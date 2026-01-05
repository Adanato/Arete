import subprocess
import sys
import time


def run_docker_cmd(args, user="0", env=None):
    cmd = ["docker", "exec", "-u", user]
    if env:
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])
    cmd.append("anki-test")
    cmd.extend(args)
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main():
    print("🔓 Unlocking Anki Container...")

    # 1. Install xdotool
    print("📦 Installing xdotool (this may take a moment)...")
    try:
        run_docker_cmd(["apt-get", "update"])
        run_docker_cmd(["apt-get", "install", "-y", "xdotool"])
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install xdotool: {e.stderr}")
        sys.exit(1)

    # 2. Find UXTerm Window
    print("🔍 Looking for Anki Launcher window...")
    found = False
    for _ in range(300):
        try:
            # Check if window exists
            run_docker_cmd(
                ["xdotool", "search", "--class", "UXTerm"], user="1000", env={"DISPLAY": ":1"}
            )
            found = True
            print("✅ Found Anki Launcher!")
            break
        except subprocess.CalledProcessError:
            time.sleep(1)
            print(".", end="", flush=True)

    if not found:
        print("\n❌ Could not find Anki Launcher window within 300s.")
        sys.exit(1)

    # 3. Bypass Launcher
    print("\n👉 Bypassing Launcher 'Press Enter'...")
    time.sleep(1)
    run_docker_cmd(
        ["xdotool", "search", "--class", "UXTerm", "windowactivate", "--sync", "key", "Return"],
        user="1000",
        env={"DISPLAY": ":1"},
    )

    # 4. Bypass Language Wizard
    print("👉 Handling Language Selection ('English' -> 'Yes')...")
    time.sleep(5)  # Wait for main window/wizard to pop

    # Select English (Enter)
    run_docker_cmd(["xdotool", "key", "Return"], user="1000", env={"DISPLAY": ":1"})
    time.sleep(2)

    # Select 'Yes' (Left -> Enter)
    run_docker_cmd(["xdotool", "key", "Left", "Return"], user="1000", env={"DISPLAY": ":1"})
    time.sleep(2)

    # Cleanup (Extra Enter)
    run_docker_cmd(["xdotool", "key", "Return"], user="1000", env={"DISPLAY": ":1"})

    print("🎉 Unlock sequence complete. Running connection check...")
    subprocess.run(["uv", "run", "scripts/wait_for_anki.py"])


if __name__ == "__main__":
    main()
