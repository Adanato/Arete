# Arete Anki Add-on

The **Arete Anki Add-on** (`arete_ankiconnect`) is a specialized bridge that allows the Arete CLI and Obsidian Plugin to communicate directly with your running Anki instance.

## Why is this needed?

While Arete can sync notes directly to the Anki database (using `AnkiDirectAdapter`), many of the real-time features require Anki to be open. The add-on provides a REST API that enables:

- **Live Hover Previews**: See your card content in Obsidian without switching apps.
- **Statistical Analytics**: Fetch real-time retention and lapse data.
- **GUI Integration**: Automatically open the Anki Browser to a specific note from Obsidian.

## Installation

### Manual Installation

1.  Download the `arete_ankiconnect.zip` from the [latest release](https://github.com/Adanato/obsidian_2_anki/releases).
2.  Open Anki.
3.  Go to `Tools` -> `Add-ons`.
4.  Click `View Files`. This opens your Anki add-ons folder.
5.  Extract the contents of the zip into a folder named `arete_ankiconnect`.
6.  Restart Anki.

### For Developers

If you are working on the project locally, you can symlink the plugin directory:

```bash
ln -s /path/to/obsidian_2_anki/arete_ankiconnect ~/Library/Application\ Support/Anki2/addons21/arete_ankiconnect
```

## Configuration

The add-on listens on port `8765` by default. You can change this in the `config.json` file within the add-on directory if needed.

```json
{
    "apiKey": null,
    "apiPort": 8765,
    "apiLogPath": null
}
```

## Troubleshooting

- **Port Conflict**: Ensure no other application (like the original AnkiConnect) is using port `8765`.
- **Anki Not Running**: The add-on only works while Anki is open.
- **Firewall**: Ensure your local firewall allows connections to port `8765`.
