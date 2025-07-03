import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import os
import subprocess

def check_and_install_requirements():
    required_packages = {
        'discord.py': 'discord.py',
        'colorama': 'colorama', 
        'requests': 'requests',
        'aiohttp': 'aiohttp',
        'python-dotenv': 'python-dotenv',
        'aiohttp-socks': 'aiohttp-socks',
        'pytz': 'pytz',
        'pyzipper': 'pyzipper'
    }
    
    def install_package(package_name):
        try:
            print(f"Installing {package_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"{package_name} installed successfully.")
            return True
        except subprocess.CalledProcessError:
            print(f"Error installing {package_name}.")
            return False

    packages_to_install = []
    try:
        import pkg_resources
        installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    except ImportError:
        install_package('setuptools')
        import pkg_resources
        installed_packages = {pkg.key for pkg in pkg_resources.working_set}

    for package, pip_name in required_packages.items():
        if package.lower() not in installed_packages:
            packages_to_install.append(pip_name)

    if packages_to_install:
        print("Missing libraries detected. Starting installation...")
        for package in packages_to_install:
            success = install_package(package)
            if not success:
                print(f"Some libraries could not be installed. Please run pip install {package} manually.")
                sys.exit(1)
        print("All required libraries installed!")
        return True
    return False

if __name__ == "__main__":
    check_and_install_requirements()
    
    import discord
    from discord.ext import commands
    import sqlite3
    from colorama import Fore, Style, init
    import requests
    import asyncio
    import pkg_resources
    import shutil
    import zipfile
    from datetime import datetime

    # Migration function to detect old system and migrate to new
    def is_legacy_version():
        """Check if this is the old autoupdateinfo.txt based system"""
        return os.path.exists("autoupdateinfo.txt") or not os.path.exists("version")

    def migrate_from_legacy():
        """Migrate from old system to new GitHub release system"""
        print(Fore.YELLOW + "Detected legacy update system. Migrating to new GitHub release system..." + Style.RESET_ALL)
        
        # Create version file - start with a reasonable version
        # Try to extract version from autoupdateinfo.txt if available
        current_version = "v1.1.0"  # Default fallback
        if os.path.exists("autoupdateinfo.txt"):
            try:
                with open("autoupdateinfo.txt", "r") as f:
                    for line in f:
                        if line.startswith("Version="):
                            old_version = line.split("=")[1].strip()
                            # Convert old format (V1.1) to new format (v1.1.0)
                            if old_version.startswith("V"):
                                old_version = old_version[1:] # Remove V
                            if old_version.count(".") == 0:
                                current_version = f"v{old_version}.0"
                            elif old_version.count(".") == 1:
                                current_version = f"v{old_version}.0"
                            else:
                                current_version = f"v{old_version}"
                            break
            except Exception as e:
                print(f"Warning: Could not parse version from autoupdateinfo.txt: {e}")
        
        with open("version", "w") as f:
            f.write(current_version)
        
        # Clean up old files
        if os.path.exists("autoupdateinfo.txt"):
            try:
                os.remove("autoupdateinfo.txt")
                print("Removed legacy autoupdateinfo.txt")
            except Exception as e:
                print(f"Warning: Could not remove autoupdateinfo.txt: {e}")
        
        print(Fore.GREEN + f"Migration completed. Now using GitHub release system (current version: {current_version})." + Style.RESET_ALL)

    # New update system based on GitHub releases
    UPDATE_SOURCES = [
        {
            "name": "GitHub",
            "api_url": "https://api.github.com/repos/justncodes/Kingshot-Discord-Bot/releases/latest",
            "primary": True
        }
    ]

    def get_latest_release_info():
        """Get latest release info from GitHub"""
        for source in UPDATE_SOURCES:
            try:
                print(f"Checking for updates from {source['name']}...")
                
                if source['name'] == "GitHub":
                    response = requests.get(source['api_url'], timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        # Use GitHub's automatic source archive
                        repo_name = source['api_url'].split('/repos/')[1].split('/releases')[0]
                        download_url = f"https://github.com/{repo_name}/archive/refs/tags/{data['tag_name']}.zip"
                        return {
                            "tag_name": data["tag_name"],
                            "body": data["body"],
                            "download_url": download_url,
                            "source": source['name']
                        }
                
            except requests.exceptions.RequestException as e:
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 404:
                        print(f"{source['name']} repository not found or no releases available")
                    elif e.response.status_code in [403, 429]:
                        print(f"{source['name']} access limited (rate limit or access denied)")
                    else:
                        print(f"{source['name']} returned HTTP {e.response.status_code}")
                else:
                    print(f"{source['name']} connection failed")
                continue
            except Exception as e:
                print(f"Failed to check {source['name']}: {e}")
                continue
        
        print("All update sources failed")
        return None

    def restart_bot():
        print(Fore.YELLOW + "\nRestarting bot..." + Style.RESET_ALL)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def setup_version_table():
        try:
            with sqlite3.connect('db/settings.sqlite') as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS versions (
                    file_name TEXT PRIMARY KEY,
                    version TEXT,
                    is_main INTEGER DEFAULT 0
                )''')
                conn.commit()
                print(Fore.GREEN + "Version table created successfully." + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"Error creating version table: {e}" + Style.RESET_ALL)

    def safe_remove_file(file_path):
        """Safely remove a file if it exists."""
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                return True
            except PermissionError:
                print(Fore.YELLOW + f"Warning: Access Denied. Could not remove '{file_path}'. Check permissions or if file is in use." + Style.RESET_ALL)
            except OSError as e:
                print(Fore.YELLOW + f"Warning: Could not remove '{file_path}': {e}" + Style.RESET_ALL)
        return False

    async def check_and_update_files():
        """New update system using GitHub releases"""
        try:
            # Check if we need to migrate from legacy system
            if is_legacy_version():
                migrate_from_legacy()

            release_info = get_latest_release_info()
            
            if release_info:
                latest_tag = release_info["tag_name"]
                source_name = release_info["source"]
                
                if os.path.exists("version"):
                    with open("version", "r") as f:
                        current_version = f.read().strip()
                else:
                    current_version = "v1.0.0"
                            
                if current_version != latest_tag:
                    print(Fore.YELLOW + f"New version available: {latest_tag} (from {source_name})" + Style.RESET_ALL)
                    print("Update Notes:")
                    print(release_info["body"])
                    print()
                    
                    response = input("Do you want to update now? (y/n): ").lower()
                    if response == 'y':
                        # Backup database if it exists
                        if os.path.exists("db") and os.path.isdir("db"):
                            print(Fore.YELLOW + "Making backup of database..." + Style.RESET_ALL)
                            
                            db_bak_path = "db.bak"
                            if os.path.exists(db_bak_path) and os.path.isdir(db_bak_path):
                                try:
                                    shutil.rmtree(db_bak_path)
                                except (PermissionError, OSError) as e:
                                    db_bak_path = f"db.bak_{int(datetime.now().timestamp())}"
                                    print(Fore.YELLOW + f"WARNING: Couldn't remove db.bak folder: {e}. Making backup with timestamp instead." + Style.RESET_ALL)

                            try:
                                shutil.copytree("db", db_bak_path)
                                print(Fore.GREEN + f"Backup completed: db → {db_bak_path}" + Style.RESET_ALL)
                            except Exception as e:
                                print(Fore.RED + f"WARNING: Failed to create database backup: {e}" + Style.RESET_ALL)
                                                
                        download_url = release_info["download_url"]
                        print(Fore.YELLOW + f"Downloading update from {source_name}..." + Style.RESET_ALL)
                        
                        safe_remove_file("package.zip")
                        download_resp = requests.get(download_url, timeout=600)
                        
                        if download_resp.status_code == 200:
                            with open("package.zip", "wb") as f:
                                f.write(download_resp.content)
                            
                            if os.path.exists("update") and os.path.isdir("update"):
                                try:
                                    shutil.rmtree("update")
                                except (PermissionError, OSError) as e:
                                    print(Fore.RED + f"WARNING: Could not remove previous update directory: {e}" + Style.RESET_ALL)
                                    return
                                
                            try:
                                with zipfile.ZipFile("package.zip", 'r') as zip_ref:
                                    zip_ref.extractall("update")
                            except Exception as e:
                                print(Fore.RED + f"ERROR: Failed to extract update package: {e}" + Style.RESET_ALL)
                                return
                                
                            safe_remove_file("package.zip")
                            
                            # Find the extracted directory (GitHub archives create a subdirectory)
                            update_dir = "update"
                            extracted_items = os.listdir(update_dir)
                            if len(extracted_items) == 1 and os.path.isdir(os.path.join(update_dir, extracted_items[0])):
                                update_dir = os.path.join(update_dir, extracted_items[0])
                            
                            # Handle main.py update
                            main_py_path = os.path.join(update_dir, "main.py")
                            if os.path.exists(main_py_path):
                                try:
                                    if os.path.exists("main.py.bak"):
                                        os.remove("main.py.bak")
                                except Exception:
                                    pass
                                    
                                try:
                                    if os.path.exists("main.py"):
                                        os.rename("main.py", "main.py.bak")
                                except Exception as e:
                                    print(Fore.YELLOW + f"Could not backup main.py: {e}" + Style.RESET_ALL)
                                    try:
                                        if os.path.exists("main.py"):
                                            os.remove("main.py")
                                            print(Fore.YELLOW + "Removed current main.py" + Style.RESET_ALL)
                                    except Exception:
                                        print(Fore.RED + "Warning: Could not backup or remove current main.py" + Style.RESET_ALL)
                                
                                try:
                                    shutil.copy2(main_py_path, "main.py")
                                except Exception as e:
                                    print(Fore.RED + f"ERROR: Could not install new main.py: {e}" + Style.RESET_ALL)
                                    return
                            
                            # Copy all other files
                            for root, _, files in os.walk(update_dir):
                                for file in files:
                                    if file == "main.py":  # Already handled
                                        continue
                                        
                                    src_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(src_path, update_dir)
                                    dst_path = os.path.join(".", rel_path)
                                    
                                    # Skip certain files that shouldn't be overwritten
                                    if file in ["bot_token.txt", "version"] or dst_path.startswith("db/") or dst_path.startswith("db\\"):
                                        continue
                                    
                                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                                    if os.path.exists(dst_path):
                                        backup_path = f"{dst_path}.bak"
                                        safe_remove_file(backup_path)
                                        try:
                                            os.rename(dst_path, backup_path)
                                        except Exception as e:
                                            print(Fore.YELLOW + f"Could not create backup of {dst_path}: {e}" + Style.RESET_ALL)
                                            
                                    try:
                                        shutil.copy2(src_path, dst_path)
                                    except Exception as e:
                                        print(Fore.RED + f"Failed to copy {file} to {dst_path}: {e}" + Style.RESET_ALL)
                            
                            try:
                                shutil.rmtree("update")
                            except Exception as e:
                                print(Fore.RED + f"WARNING: update folder could not be removed: {e}. You may want to remove it manually." + Style.RESET_ALL)
                            
                            # Update version file
                            with open("version", "w") as f:
                                f.write(latest_tag)
                            
                            print(Fore.GREEN + f"Update completed successfully from {source_name}." + Style.RESET_ALL)
                            restart_bot()
                        else:
                            print(Fore.RED + f"Failed to download the update from {source_name}. HTTP status: {download_resp.status_code}" + Style.RESET_ALL)
                            return  
                else:
                    print(Fore.GREEN + "Bot is up to date!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Failed to fetch latest release info" + Style.RESET_ALL)
                
        except Exception as e:
            print(Fore.RED + f"Error during update check: {e}" + Style.RESET_ALL)

    # Initialize colorama and setup
    init(autoreset=True)
    
    # Setup database folder and connections
    if not os.path.exists("db"):
        os.makedirs("db")
        print(Fore.GREEN + "db folder created" + Style.RESET_ALL)

    setup_version_table()

    # Run update check
    asyncio.run(check_and_update_files())
            
    import discord
    from discord.ext import commands

    class CustomBot(commands.Bot):
        async def on_error(self, event_name, *args, **kwargs):
            if event_name == "on_interaction":
                error = sys.exc_info()[1]
                if isinstance(error, discord.NotFound) and error.code == 10062:
                    return
            
            await super().on_error(event_name, *args, **kwargs)

        async def on_command_error(self, ctx, error):
            if isinstance(error, discord.NotFound) and error.code == 10062:
                return
            await super().on_command_error(ctx, error)

    intents = discord.Intents.default()
    intents.message_content = True

    bot = CustomBot(command_prefix="/", intents=intents)

    # Token handling
    token_file = "bot_token.txt"
    if not os.path.exists(token_file):
        bot_token = input("Enter the bot token: ")
        with open(token_file, "w") as f:
            f.write(bot_token)
    else:
        with open(token_file, "r") as f:
            bot_token = f.read().strip()

    # Database setup
    databases = {
        "conn_alliance": "db/alliance.sqlite",
        "conn_giftcode": "db/giftcode.sqlite",
        "conn_changes": "db/changes.sqlite",
        "conn_users": "db/users.sqlite",
        "conn_settings": "db/settings.sqlite",
    }

    connections = {name: sqlite3.connect(path) for name, path in databases.items()}

    print(Fore.GREEN + "Database connections have been successfully established." + Style.RESET_ALL)

    def create_tables():
        with connections["conn_changes"] as conn_changes:
            conn_changes.execute("""CREATE TABLE IF NOT EXISTS nickname_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                fid INTEGER, 
                old_nickname TEXT, 
                new_nickname TEXT, 
                change_date TEXT
            )""")
            
            conn_changes.execute("""CREATE TABLE IF NOT EXISTS furnace_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                fid INTEGER, 
                old_furnace_lv INTEGER, 
                new_furnace_lv INTEGER, 
                change_date TEXT
            )""")

        with connections["conn_settings"] as conn_settings:
            conn_settings.execute("""CREATE TABLE IF NOT EXISTS botsettings (
                id INTEGER PRIMARY KEY, 
                channelid INTEGER, 
                giftcodestatus TEXT 
            )""")
            
            conn_settings.execute("""CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY, 
                is_initial INTEGER
            )""")

        with connections["conn_users"] as conn_users:
            conn_users.execute("""CREATE TABLE IF NOT EXISTS users (
                fid INTEGER PRIMARY KEY, 
                nickname TEXT, 
                furnace_lv INTEGER DEFAULT 0, 
                kid INTEGER, 
                stove_lv_content TEXT, 
                alliance TEXT
            )""")

        with connections["conn_giftcode"] as conn_giftcode:
            conn_giftcode.execute("""CREATE TABLE IF NOT EXISTS gift_codes (
                giftcode TEXT PRIMARY KEY, 
                date TEXT
            )""")
            
            conn_giftcode.execute("""CREATE TABLE IF NOT EXISTS user_giftcodes (
                fid INTEGER, 
                giftcode TEXT, 
                status TEXT, 
                PRIMARY KEY (fid, giftcode),
                FOREIGN KEY (giftcode) REFERENCES gift_codes (giftcode)
            )""")

        with connections["conn_alliance"] as conn_alliance:
            conn_alliance.execute("""CREATE TABLE IF NOT EXISTS alliancesettings (
                alliance_id INTEGER PRIMARY KEY, 
                channel_id INTEGER, 
                interval INTEGER
            )""")
            
            conn_alliance.execute("""CREATE TABLE IF NOT EXISTS alliance_list (
                alliance_id INTEGER PRIMARY KEY, 
                name TEXT
            )""")

        print(Fore.GREEN + "All tables checked." + Style.RESET_ALL)

    create_tables()

    async def load_cogs():
        cogs = ["olddb", "control", "alliance", "alliance_member_operations", "bot_operations", "logsystem", "support_operations", "gift_operations", "changes", "w", "wel", "other_features", "bear_trap", "id_channel", "backup_operations", "bear_trap_editor"]
        
        for cog in cogs:
            try:
                await bot.load_extension(f"cogs.{cog}")
            except Exception as e:
                print(f"✗ Failed to load cog {cog}: {e}")

    @bot.event
    async def on_ready():
        try:
            print(f"{Fore.GREEN}Logged in as {Fore.CYAN}{bot.user}{Style.RESET_ALL}")
            await bot.tree.sync()
        except Exception as e:
            print(f"Error syncing commands: {e}")

    async def main():
        await load_cogs()
        await bot.start(bot_token)

    if __name__ == "__main__":
        asyncio.run(main())