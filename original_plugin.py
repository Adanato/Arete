# Copyright 2016-2021 Alex Yatskov
# Copyright 2024 Arete Team
#
# Unified Anki Add-on: AnkiConnect + Arete Source Navigation
#

import aqt

anki_version = tuple(int(segment) for segment in aqt.appVersion.split("."))

if anki_version < (2, 1, 45):
    raise Exception("Minimum Anki version supported: 2.1.45")

import base64
import glob
import hashlib
import inspect
import json
import os
import os.path
import platform
import re
import time
import unicodedata
import webbrowser
from urllib.parse import quote

import anki
import anki.exporting
import anki.storage
from anki.cards import Card
from anki.consts import MODEL_CLOZE
from anki.errors import NotFoundError
from anki.exporting import AnkiPackageExporter
from anki.importing import AnkiPackageImporter
from anki.notes import Note
from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.qt import QAction, QCheckBox, QKeySequence, QMenu, QMessageBox, Qt, QTimer
from aqt.reviewer import Reviewer
from aqt.utils import showWarning, tooltip

from . import util, web
from .edit import Edit
from .web import format_exception_reply, format_success_reply

# ─────────────────────────────────────────────────────────────────────────────
# Arete Config & Logic
# ─────────────────────────────────────────────────────────────────────────────

ADDON_PATH = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_PATH, "config.json")
CONFIG = {}

def load_config():
    global CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                CONFIG = json.load(f)
        except Exception:
            CONFIG = {}

load_config()

def get_obsidian_source(note) -> tuple[str, str, int] | None:
    """
    Extract Obsidian source info from note's _obsidian_source field.
    Returns (vault_name, file_path, card_index) or None if not found.
    """
    for field_name in note.keys():
        if field_name == "_obsidian_source":
            field_value = note[field_name]
            if field_value:
                # Strip HTML tags if any (legacy sync issues)
                import re
                clean_value = re.sub(r'<[^>]*>', '', field_value).strip()

                # Format: vault|path|index
                parts = clean_value.split("|")
                if len(parts) >= 3:
                    vault = parts[0]
                    file_path = parts[1]
                    try:
                        card_idx = int(parts[2])
                    except ValueError:
                        card_idx = 1
                    return vault, file_path, card_idx
    return None


def open_obsidian_uri(vault: str, file_path: str, card_idx: int = 1) -> bool:
    """
    Open Obsidian via URI scheme.
    Returns True on success, False on failure.
    """
    # Allow config to override vault name
    actual_vault = CONFIG.get("vault_name_override", vault) or vault

    encoded_vault = quote(actual_vault)
    encoded_path = quote(file_path)

    # Use Advanced URI for line-level navigation (requires Advanced URI plugin in Obsidian)
    uri = f"obsidian://advanced-uri?vault={encoded_vault}&filepath={encoded_path}&line={card_idx}"

    # Fallback: Standard URI (no line navigation, but works without plugins)
    # uri = f"obsidian://open?vault={encoded_vault}&file={encoded_path}"

    try:
        webbrowser.open(uri)
        return True
    except Exception as e:
        showWarning(f"Failed to open Obsidian: {e}")
        return False


def open_current_card_in_obsidian():
    """Open current reviewing card's source in Obsidian."""
    reviewer = mw.reviewer
    if not reviewer or not reviewer.card:
        showWarning("No card is currently being reviewed.")
        return

    note = reviewer.card.note()
    source = get_obsidian_source(note)

    if not source:
        showWarning(
            "No Obsidian source found for this card.\n\n"
            "Make sure the card was synced with arete and has the "
            "'_obsidian_source' field."
        )
        return

    vault, file_path, card_idx = source
    if open_obsidian_uri(vault, file_path, card_idx):
        tooltip(f"Opening in Obsidian: {file_path}")


def setup_reviewer_shortcut():
    """Add keyboard shortcut and menu item."""
    action = QAction("Open in Obsidian", mw)
    action.setShortcut(QKeySequence("Ctrl+Shift+O"))
    action.triggered.connect(open_current_card_in_obsidian)
    mw.form.menuTools.addAction(action)


def on_browser_context_menu(browser: Browser, menu: QMenu):
    """Add 'Open in Obsidian' to browser right-click menu."""
    selected = browser.selectedNotes()
    if not selected:
        return

    action = menu.addAction("Open in Obsidian")
    action.triggered.connect(lambda: open_selected_notes_in_obsidian(browser))


def open_selected_notes_in_obsidian(browser: Browser):
    """Open selected notes in Obsidian (first one if multiple selected)."""
    selected = browser.selectedNotes()
    if not selected:
        showWarning("No notes selected.")
        return

    # Open first selected note
    note_id = selected[0]
    note = mw.col.get_note(note_id)

    source = get_obsidian_source(note)
    if not source:
        showWarning(
            "No Obsidian source found for this note.\n\n"
            "Make sure the note was synced with arete and has the "
            "'_obsidian_source' field."
        )
        return

    vault, file_path, card_idx = source
    if open_obsidian_uri(vault, file_path, card_idx):
        tooltip(f"Opening in Obsidian: {file_path}")

    # If multiple selected, notify user
    if len(selected) > 1:
        tooltip(f"Opened first of {len(selected)} selected notes")


# ─────────────────────────────────────────────────────────────────────────────
# AnkiConnect Class (with getFSRSStats)
# ─────────────────────────────────────────────────────────────────────────────

class AnkiConnect:
    def __init__(self):
        self.log = None
        self.timer = None
        self.server = web.WebServer(self.handler)

    def initLogging(self):
        logPath = util.setting('apiLogPath')
        if logPath is not None:
            self.log = open(logPath, 'w')

    def startWebServer(self):
        try:
            self.server.listen()

            # only keep reference to prevent garbage collection
            self.timer = QTimer()
            self.timer.timeout.connect(self.advance)
            self.timer.start(util.setting('apiPollInterval'))
        except:
            QMessageBox.critical(
                self.window(),
                'AnkiConnect',
                'Failed to listen on port {}.\nMake sure it is available and is not in use.'.format(util.setting('webBindPort'))
            )

    def save_model(self, models, ankiModel):
        models.update_dict(ankiModel)

    def logEvent(self, name, data):
        if self.log is not None:
            self.log.write(f'[{name}]\n')
            json.dump(data, self.log, indent=4, sort_keys=True)
            self.log.write('\n\n')
            self.log.flush()


    def advance(self):
        self.server.advance()


    def handler(self, request):
        self.logEvent('request', request)

        name = request.get('action', '')
        version = request.get('version', 4)
        params = request.get('params', {})
        key = request.get('key')

        try:
            if key != util.setting('apiKey') and name != 'requestPermission':
                raise Exception('valid api key must be provided')

            method = None

            for methodName, methodInst in inspect.getmembers(self, predicate=inspect.ismethod):
                apiVersionLast = 0
                apiNameLast = None

                if getattr(methodInst, 'api', False):
                    for apiVersion, apiName in getattr(methodInst, 'versions', []):
                        if apiVersionLast < apiVersion <= version:
                            apiVersionLast = apiVersion
                            apiNameLast = apiName

                    if apiNameLast is None and apiVersionLast == 0:
                        apiNameLast = methodName

                    if apiNameLast is not None and apiNameLast == name:
                        method = methodInst
                        break

            if method is None:
                raise Exception('unsupported action')

            api_return_value = methodInst(**params)
            reply = format_success_reply(version, api_return_value)

        except Exception as e:
            reply = format_exception_reply(version, e)

        self.logEvent('reply', reply)
        return reply


    def window(self):
        return aqt.mw


    def reviewer(self):
        reviewer = self.window().reviewer
        if reviewer is None:
            raise Exception('reviewer is not available')

        return reviewer


    def collection(self):
        collection = self.window().col
        if collection is None:
            raise Exception('collection is not available')

        return collection


    def decks(self):
        decks = self.collection().decks
        if decks is None:
            raise Exception('decks are not available')

        return decks


    def scheduler(self):
        scheduler = self.collection().sched
        if scheduler is None:
            raise Exception('scheduler is not available')

        return scheduler


    def database(self):
        database = self.collection().db
        if database is None:
            raise Exception('database is not available')

        return database


    def media(self):
        media = self.collection().media
        if media is None:
            raise Exception('media is not available')

        return media


    def getModel(self, modelName):
        model = self.collection().models.byName(modelName)
        if model is None:
            raise Exception(f'model was not found: {modelName}')
        return model


    def getField(self, model, fieldName):
        fieldMap = self.collection().models.fieldMap(model)
        if fieldName not in fieldMap:
            raise Exception('field was not found in {}: {}'.format(model['name'], fieldName))
        return fieldMap[fieldName][1]


    def getTemplate(self, model, templateName):
        for ankiTemplate in model['tmpls']:
            if ankiTemplate['name'] == templateName:
                return ankiTemplate
        raise Exception('template was not found in {}: {}'.format(model['name'], templateName))


    def startEditing(self):
        self.window().requireReset()


    def stopEditing(self):
        if self.collection() is not None:
            self.window().maybeReset()


    def createNote(self, note):
        collection = self.collection()

        model = collection.models.byName(note['modelName'])
        if model is None:
            raise Exception('model was not found: {}'.format(note['modelName']))

        deck = collection.decks.byName(note['deckName'])
        if deck is None:
            raise Exception('deck was not found: {}'.format(note['deckName']))

        ankiNote = anki.notes.Note(collection, model)
        ankiNote.model()['did'] = deck['id']
        if 'tags' in note:
            ankiNote.tags = note['tags']

        for name, value in note['fields'].items():
            for ankiName in ankiNote.keys():
                if name.lower() == ankiName.lower():
                    ankiNote[ankiName] = value
                    break

        self.addMediaFromNote(ankiNote, note)

        allowDuplicate = False
        duplicateScope = None
        duplicateScopeDeckName = None
        duplicateScopeCheckChildren = False
        duplicateScopeCheckAllModels = False

        if 'options' in note:
            options = note['options']
            if 'allowDuplicate' in options:
                allowDuplicate = options['allowDuplicate']
                if type(allowDuplicate) is not bool:
                    raise Exception('option parameter "allowDuplicate" must be boolean')
            if 'duplicateScope' in options:
                duplicateScope = options['duplicateScope']
            if 'duplicateScopeOptions' in options:
                duplicateScopeOptions = options['duplicateScopeOptions']
                if 'deckName' in duplicateScopeOptions:
                    duplicateScopeDeckName = duplicateScopeOptions['deckName']
                if 'checkChildren' in duplicateScopeOptions:
                    duplicateScopeCheckChildren = duplicateScopeOptions['checkChildren']
                    if type(duplicateScopeCheckChildren) is not bool:
                        raise Exception('option parameter "duplicateScopeOptions.checkChildren" must be boolean')
                if 'checkAllModels' in duplicateScopeOptions:
                    duplicateScopeCheckAllModels = duplicateScopeOptions['checkAllModels']
                    if type(duplicateScopeCheckAllModels) is not bool:
                        raise Exception('option parameter "duplicateScopeOptions.checkAllModels" must be boolean')

        duplicateOrEmpty = self.isNoteDuplicateOrEmptyInScope(
            ankiNote,
            deck,
            collection,
            duplicateScope,
            duplicateScopeDeckName,
            duplicateScopeCheckChildren,
            duplicateScopeCheckAllModels
        )

        if duplicateOrEmpty == 1:
            raise Exception('cannot create note because it is empty')
        elif duplicateOrEmpty == 2:
            if allowDuplicate:
                return ankiNote
            raise Exception('cannot create note because it is a duplicate')
        elif duplicateOrEmpty == 0:
            return ankiNote
        else:
            raise Exception('cannot create note for unknown reason')


    def isNoteDuplicateOrEmptyInScope(
        self,
        note,
        deck,
        collection,
        duplicateScope,
        duplicateScopeDeckName,
        duplicateScopeCheckChildren,
        duplicateScopeCheckAllModels
    ):
        # Returns: 1 if first is empty, 2 if first is a duplicate, 0 otherwise.

        # note.dupeOrEmpty returns if a note is a global duplicate with the specific model.
        # This is used as the default check, and the rest of this function is manually
        # checking if the note is a duplicate with additional options.
        if duplicateScope != 'deck' and not duplicateScopeCheckAllModels:
            return note.dupeOrEmpty() or 0

        # Primary field for uniqueness
        val = note.fields[0]
        if not val.strip():
            return 1
        csum = anki.utils.fieldChecksum(val)

        # Create dictionary of deck ids
        dids = None
        if duplicateScope == 'deck':
            did = deck['id']
            if duplicateScopeDeckName is not None:
                deck2 = collection.decks.byName(duplicateScopeDeckName)
                if deck2 is None:
                    # Invalid deck, so cannot be duplicate
                    return 0
                did = deck2['id']

            dids = {did: True}
            if duplicateScopeCheckChildren:
                for kv in collection.decks.children(did):
                    dids[kv[1]] = True

        # Build query
        query = 'select id from notes where csum=?'
        queryArgs = [csum]
        if note.id:
            query += ' and id!=?'
            queryArgs.append(note.id)
        if not duplicateScopeCheckAllModels:
            query += ' and mid=?'
            queryArgs.append(note.mid)

        # Search
        for noteId in note.col.db.list(query, *queryArgs):
            if dids is None:
                # Duplicate note exists in the collection
                return 2
            # Validate that a card exists in one of the specified decks
            for cardDeckId in note.col.db.list('select did from cards where nid=?', noteId):
                if cardDeckId in dids:
                    return 2

        # Not a duplicate
        return 0

    def raiseNotFoundError(self, errorMsg):
        if anki_version < (2, 1, 55):
            raise NotFoundError(errorMsg)
        raise NotFoundError(errorMsg, None, None, None)

    def getCard(self, card_id: int) -> Card:
        try:
            return self.collection().getCard(card_id)
        except NotFoundError:
            self.raiseNotFoundError(f'Card was not found: {card_id}')

    def getNote(self, note_id: int) -> Note:
        try:
            return self.collection().getNote(note_id)
        except NotFoundError:
            self.raiseNotFoundError(f'Note was not found: {note_id}')

    def deckStatsToJson(self, due_tree):
        deckStats = {'deck_id': due_tree.deck_id,
                     'name': due_tree.name,
                     'new_count': due_tree.new_count,
                     'learn_count': due_tree.learn_count,
                     'review_count': due_tree.review_count}
        if anki_version > (2, 1, 46):
            # total_in_deck is not supported on lower Anki versions
            deckStats['total_in_deck'] = due_tree.total_in_deck
        return deckStats

    def collectDeckTreeChildren(self, parent_node):
        allNodes = {parent_node.deck_id: parent_node}
        for child in parent_node.children:
            for deckId, childNode in self.collectDeckTreeChildren(child).items():
                allNodes[deckId] = childNode
        return allNodes

    #
    # Miscellaneous
    #

    @util.api()
    def version(self):
        return util.setting('apiVersion')


    @util.api()
    def requestPermission(self, origin, allowed):
        results = {
                "permission": "denied",
        }

        if allowed:
            results = {
                    "permission": "granted",
                    "requireApikey": bool(util.setting('apiKey')),
                    "version": util.setting('apiVersion')
            }

        elif origin in util.setting('ignoreOriginList'):
            pass  # defaults to denied

        else:  # prompt the user
            msg = QMessageBox(None)
            msg.setWindowTitle("A website wants to access to Anki")
            msg.setText(f'"{origin}" requests permission to use Anki through AnkiConnect. Do you want to give it access?')
            msg.setInformativeText("By granting permission, you'll allow the website to modify your collection on your behalf, including the execution of destructive actions such as deck deletion.")
            msg.setWindowIcon(self.window().windowIcon())
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Yes|QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            msg.setCheckBox(QCheckBox(text=f'Ignore further requests from "{origin}"', parent=msg))
            msg.setWindowFlags(Qt.WindowStaysOnTopHint)
            pressedButton = msg.exec_()

            if pressedButton == QMessageBox.Yes:
                config = aqt.mw.addonManager.getConfig(__name__)
                config["webCorsOriginList"] = util.setting('webCorsOriginList')
                config["webCorsOriginList"].append(origin)
                aqt.mw.addonManager.writeConfig(__name__, config)
                results = {
                    "permission": "granted",
                    "requireApikey": bool(util.setting('apiKey')),
                    "version": util.setting('apiVersion')
                }

            # if the origin isn't an empty string, the user clicks "No", and the ignore box is checked
            elif origin and pressedButton == QMessageBox.No and msg.checkBox().isChecked():
                config = aqt.mw.addonManager.getConfig(__name__)
                config["ignoreOriginList"] = util.setting('ignoreOriginList')
                config["ignoreOriginList"].append(origin)
                aqt.mw.addonManager.writeConfig(__name__, config)

            # else defaults to denied

        return results


    @util.api()
    def getProfiles(self):
        return self.window().pm.profiles()


    @util.api()
    def loadProfile(self, name):
        if name not in self.window().pm.profiles():
            return False

        if self.window().isVisible():
            cur_profile = self.window().pm.name
            if cur_profile != name:
                self.window().unloadProfileAndShowProfileManager()

                def waiter():
                    # This function waits until main window is closed
                    # It's needed cause sync can take quite some time
                    # And if we call loadProfile until sync is ended things will go wrong
                    if self.window().isVisible():
                        QTimer.singleShot(1000, waiter)
                    else:
                        self.loadProfile(name)

                waiter()
        else:
            self.window().pm.load(name)
            self.window().loadProfile()
            self.window().profileDiag.closeWithoutQuitting()

        return True


    @util.api()
    def sync(self):
        self.window().onSync()


    @util.api()
    def multi(self, actions):
        return list(map(self.handler, actions))


    @util.api()
    def getNumCardsReviewedToday(self):
        return self.database().scalar('select count() from revlog where id > ?', (self.scheduler().dayCutoff - 86400) * 1000)

    @util.api()
    def getNumCardsReviewedByDay(self):
        return self.database().all('select date(id/1000 - ?, "unixepoch", "localtime") as day, count() from revlog group by day order by day desc',
                                    int(time.strftime("%H", time.localtime(self.scheduler().dayCutoff))) * 3600)


    @util.api()
    def getCollectionStatsHTML(self, wholeCollection=True):
        stats = self.collection().stats()
        stats.wholeCollection = wholeCollection
        return stats.report()


    #
    # Decks
    #

    @util.api()
    def deckNames(self):
        return self.decks().allNames()


    @util.api()
    def deckNamesAndIds(self):
        decks = {}
        for deck in self.deckNames():
            decks[deck] = self.decks().id(deck)

        return decks


    @util.api()
    def getDecks(self, cards):
        decks = {}
        for card in cards:
            did = self.database().scalar('select did from cards where id=?', card)
            deck = self.decks().get(did)['name']
            if deck in decks:
                decks[deck].append(card)
            else:
                decks[deck] = [card]

        return decks


    @util.api()
    def createDeck(self, deck):
        try:
            self.startEditing()
            did = self.decks().id(deck)
        finally:
            self.stopEditing()

        return did


    @util.api()
    def changeDeck(self, cards, deck):
        self.startEditing()

        did = self.collection().decks.id(deck)
        mod = anki.utils.intTime()
        usn = self.collection().usn()

        # normal cards
        scids = anki.utils.ids2str(cards)
        # remove any cards from filtered deck first
        self.collection().sched.remFromDyn(cards)

        # then move into new deck
        self.collection().db.execute('update cards set usn=?, mod=?, did=? where id in ' + scids, usn, mod, did)
        self.stopEditing()


    @util.api()
    def deleteDecks(self, decks, cardsToo=False):
        if not cardsToo:
            # since f592672fa952260655881a75a2e3c921b2e23857 (2.1.28)
            # (see anki$ git log "-Gassert cardsToo")
            # you can't delete decks without deleting cards as well.
            # however, since 62c23c6816adf912776b9378c008a52bb50b2e8d (2.1.45)
            # passing cardsToo to `rem` (long deprecated) won't raise an error!
            # this is dangerous, so let's raise our own exception
            raise Exception("Since Anki 2.1.28 it's not possible "
                            "to delete decks without deleting cards as well")
        try:
            self.startEditing()
            decks = filter(lambda d: d in self.deckNames(), decks)
            for deck in decks:
                did = self.decks().id(deck)
                self.decks().rem(did, cardsToo=cardsToo)
        finally:
            self.stopEditing()


    @util.api()
    def getDeckConfig(self, deck):
        if deck not in self.deckNames():
            return False

        collection = self.collection()
        did = collection.decks.id(deck)
        return collection.decks.confForDid(did)


    @util.api()
    def saveDeckConfig(self, config):
        collection = self.collection()

        config['id'] = str(config['id'])
        config['mod'] = anki.utils.intTime()
        config['usn'] = collection.usn()
        if int(config['id']) not in [c['id'] for c in collection.decks.all_config()]:
            return False
        try:
            collection.decks.save(config)
            collection.decks.updateConf(config)
        except:
            return False
        return True


    @util.api()
    def setDeckConfigId(self, decks, configId):
        configId = int(configId)
        for deck in decks:
            if deck not in self.deckNames():
                return False

        collection = self.collection()

        for deck in decks:
            try:
                did = str(collection.decks.id(deck))
                deck_dict = aqt.mw.col.decks.decks[did]
                deck_dict['conf'] = configId
                collection.decks.save(deck_dict)
            except:
                return False

        return True


    @util.api()
    def cloneDeckConfigId(self, name, cloneFrom='1'):
        configId = int(cloneFrom)
        collection = self.collection()
        if configId not in [c['id'] for c in collection.decks.all_config()]:
            return False

        config = collection.decks.getConf(configId)
        return collection.decks.confId(name, config)


    @util.api()
    def removeDeckConfigId(self, configId):
        collection = self.collection()
        if int(configId) not in [c['id'] for c in collection.decks.all_config()]:
            return False

        collection.decks.remConf(configId)
        return True

    @util.api()
    def getDeckStats(self, decks):
        collection = self.collection()
        scheduler = self.scheduler()
        responseDict = {}
        deckIds = [collection.decks.id(d) for d in decks]

        allDeckNodes = self.collectDeckTreeChildren(scheduler.deck_due_tree())
        for deckId, deckNode in allDeckNodes.items():
            if deckId in deckIds:
                responseDict[deckId] = self.deckStatsToJson(deckNode)
        return responseDict

    @util.api()
    def storeMediaFile(self, filename, data=None, path=None, url=None, skipHash=None, deleteExisting=True):
        if not (data or path or url):
            raise Exception('You must provide a "data", "path", or "url" field.')
        if data:
            mediaData = base64.b64decode(data)
        elif path:
            with open(path, 'rb') as f:
                mediaData = f.read()
        elif url:
            mediaData = util.download(url)

        if skipHash is None:
            skip = False
        else:
            m = hashlib.md5()
            m.update(mediaData)
            skip = skipHash == m.hexdigest()

        if skip:
            return None
        if deleteExisting:
            self.deleteMediaFile(filename)
        return self.media().writeData(filename, mediaData)


    @util.api()
    def retrieveMediaFile(self, filename):
        filename = os.path.basename(filename)
        filename = unicodedata.normalize('NFC', filename)
        filename = self.media().stripIllegal(filename)

        path = os.path.join(self.media().dir(), filename)
        if os.path.exists(path):
            with open(path, 'rb') as file:
                return base64.b64encode(file.read()).decode('ascii')

        return False


    @util.api()
    def getMediaFilesNames(self, pattern='*'):
        path = os.path.join(self.media().dir(), pattern)
        return [os.path.basename(p) for p in glob.glob(path)]


    @util.api()
    def deleteMediaFile(self, filename):
        try:
            self.media().syncDelete(filename)
        except AttributeError:
            self.media().trash_files([filename])

    @util.api()
    def getMediaDirPath(self):
        return os.path.abspath(self.media().dir())

    @util.api()
    def addNote(self, note):
        ankiNote = self.createNote(note)

        collection = self.collection()
        self.startEditing()
        nCardsAdded = collection.addNote(ankiNote)
        if nCardsAdded < 1:
            raise Exception('The field values you have provided would make an empty question on all cards.')
        collection.autosave()
        self.stopEditing()

        return ankiNote.id


    def addMediaFromNote(self, ankiNote, note):
        audioObjectOrList = note.get('audio')
        self.addMedia(ankiNote, audioObjectOrList, util.MediaType.Audio)

        videoObjectOrList = note.get('video')
        self.addMedia(ankiNote, videoObjectOrList, util.MediaType.Video)

        pictureObjectOrList = note.get('picture')
        self.addMedia(ankiNote, pictureObjectOrList, util.MediaType.Picture)



    def addMedia(self, ankiNote, mediaObjectOrList, mediaType):
        if mediaObjectOrList is None:
            return

        if isinstance(mediaObjectOrList, list):
            mediaList = mediaObjectOrList
        else:
            mediaList = [mediaObjectOrList]

        for media in mediaList:
            if media is not None and len(media['fields']) > 0:
                try:
                    mediaFilename = self.storeMediaFile(media['filename'],
                                                        data=media.get('data'),
                                                        path=media.get('path'),
                                                        url=media.get('url'),
                                                        skipHash=media.get('skipHash'),
                                                        deleteExisting=media.get('deleteExisting'))

                    if mediaFilename is not None:
                        for field in media['fields']:
                            if field in ankiNote:
                                if mediaType is util.MediaType.Picture:
                                    ankiNote[field] += f'<img src="{mediaFilename}">'
                                elif mediaType is util.MediaType.Audio or mediaType is util.MediaType.Video:
                                    ankiNote[field] += f'[sound:{mediaFilename}]'

                except Exception as e:
                    errorMessage = str(e).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    for field in media['fields']:
                        if field in ankiNote:
                            ankiNote[field] += errorMessage


    @util.api()
    def canAddNote(self, note):
        try:
            return bool(self.createNote(note))
        except:
            return False

    @util.api()
    def guiCheckDatabase(self):
        self.window().onCheckDB()
        return True


    @util.api()
    def addNotes(self, notes):
        results = []
        for note in notes:
            try:
                results.append(self.addNote(note))
            except:
                results.append(None)

        return results


    @util.api()
    def canAddNotes(self, notes):
        results = []
        for note in notes:
            results.append(self.canAddNote(note))

        return results


    @util.api()
    def exportPackage(self, deck, path, includeSched=False):
        collection = self.collection()
        if collection is not None:
            deck = collection.decks.byName(deck)
            if deck is not None:
                exporter = AnkiPackageExporter(collection)
                exporter.did = deck['id']
                exporter.includeSched = includeSched
                exporter.exportInto(path)
                return True

        return False


    @util.api()
    def importPackage(self, path):
        collection = self.collection()
        if collection is not None:
            try:
                self.startEditing()
                importer = AnkiPackageImporter(collection, path)
                importer.run()
            except:
                self.stopEditing()
                raise
            else:
                self.stopEditing()
                return True

        return False


    @util.api()
    def apiReflect(self, scopes=None, actions=None):
        if not isinstance(scopes, list):
            raise Exception('scopes has invalid value')
        if not (actions is None or isinstance(actions, list)):
            raise Exception('actions has invalid value')

        cls = type(self)
        scopes2 = []
        result = {'scopes': scopes2}

        if 'actions' in scopes:
            if actions is None:
                actions = dir(cls)

            methodNames = []
            for methodName in actions:
                if not isinstance(methodName, str):
                    pass
                method = getattr(cls, methodName, None)
                if method is not None and getattr(method, 'api', False):
                    methodNames.append(methodName)

            scopes2.append('actions')
            result['actions'] = methodNames

        return result


    @util.api()
    def getFSRSStats(self, cards=None):
        if cards is None:
            cards = []
        result = []
        try:
            col = self.collection()
            if not col:
                return [{"error": "Collection is None", "cardId": -1}]
        except Exception as e:
            return [{"error": f"Collection access failed: {e}", "cardId": -1}]

        for cid in cards:
            item = {"cardId": cid, "difficulty": None, "debug": []}
            try:
                try:
                    cid = int(cid)
                except:
                    item["debug"].append(f"Invalid CID type: {type(cid)}")
                card = None
                try:
                    card = col.getCard(cid)
                except AttributeError:
                    try:
                        card = col.get_card(cid)
                    except AttributeError:
                         item["debug"].append("No get_card or getCard method")
                except Exception as e:
                     item["debug"].append(f"get_card exception: {e}")
                if not card:
                    item["debug"].append("Card not found")
                    result.append(item)
                    continue

                found_data = False
                if hasattr(card, 'memory_state'):
                    if card.memory_state:
                         item["difficulty"] = card.memory_state.difficulty
                         item["source"] = "memory_state"
                         found_data = True

                if not found_data:
                    if hasattr(card, 'data'):
                         if card.data:
                            try:
                                import json
                                data = json.loads(card.data)
                                if 'd' in data:
                                    item["difficulty"] = data['d']
                                    item["source"] = "data_json"
                            except Exception:
                                pass

                result.append(item)
            except Exception as e:
                result.append({"cardId": cid, "error": f"Outer loop error: {e}"})
        return result


#
# Entry
#

# when run inside Anki, `__name__` would be either numeric,
# or, if installed via `link.sh`, `AnkiConnectDev`
if __name__ != "plugin":
    if platform.system() == "Windows" and anki_version == (2, 1, 50):
        util.patch_anki_2_1_50_having_null_stdout_on_windows()

    Edit.register_with_anki()

    # Start AnkiConnect
    ac = AnkiConnect()
    ac.initLogging()
    ac.startWebServer()

    # Initialize Arete Hooks
    setup_reviewer_shortcut()
    gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)
