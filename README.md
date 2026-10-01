# DocTrace

Ask questions about your own documents and find **exactly where** the answer is:
which folder, which file, which page, slide or sheet.

- Point it at a folder with any nested folder structure (semesters, subjects, projects, ...).
- It indexes PDFs, Word, PowerPoint, Excel, text/Markdown, notebooks, code and, with OCR, images and scanned PDFs.
- It combines **semantic search** (meaning) with **keyword search** (exact terms like `3NF` or `TCP`).
- It can optionally write an **answer with citations** using a local LLM through [Ollama](https://ollama.com).
- Everything runs locally. Your files never leave your machine, and Gradio and Hugging Face telemetry are switched off.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Install and first run](#2-install-and-first-run)
3. [Using the app](#3-using-the-app)
4. [Settings (`.env`)](#4-settings-env)
5. [Optional extras](#5-optional-extras): AI answers, OCR, GPU, Google Drive, Docker, other devices
6. [Terminal commands](#6-terminal-commands)
7. [Updating, moving and uninstalling](#7-updating-moving-and-uninstalling)
8. [Troubleshooting](#8-troubleshooting)
9. [Supported files](#9-supported-files)
10. [How it works](#10-how-it-works) / [Project structure](#project-structure) / [Development](#development)

---

## 1. What you need

| | |
|---|---|
| **Operating system** | Windows 10/11, macOS (Apple Silicon recommended), or Linux |
| **Memory** | 8 GB RAM is enough for search and the default AI model |
| **Python** | 3.10, 3.11, 3.12 or 3.13 (3.12 recommended). See below |
| **Disk space** | About 1.5 GB for the app's environment, plus about 2 GB if you add AI answers (Ollama model) |
| **Internet** | Only for the first setup (downloads packages and the ~90 MB search model). After that it works offline |
| **Git** | Optional. Without it, download the ZIP instead (step 1 below) |

**Installing Python**, if you don't have it:

- **Windows:** nothing to do in advance. If Python is missing, setup offers to install Python 3.12 for you (see step 3). To install it yourself instead, open [python.org/downloads/windows](https://www.python.org/downloads/windows/), scroll to the newest **Python 3.12.x** release, download the **Windows installer (64-bit)**, and tick **"Add python.exe to PATH"** on the installer's first screen.
- **macOS:** `brew install python@3.12` (needs [Homebrew](https://brew.sh)), or the **macOS 64-bit universal2 installer** for the newest Python 3.12.x from [python.org/downloads/macos](https://www.python.org/downloads/macos/). The `python3` that comes with macOS is too old. If a pop-up offers to install "command line developer tools", you can click **Cancel**: you don't need them.
- **Ubuntu/Debian:** `sudo apt install python3 python3-venv`. Fedora: `sudo dnf install python3`.

Why 3.12? python.org's big yellow download button may offer a newer version (3.14+). Setup accepts it, but some packages may not support it yet. Python 3.12 always works.

To check your version, run `python --version` (Windows) or `python3 --version` (macOS/Linux) in a terminal.

**Opening a terminal in a folder** (needed for some steps):

- **Windows:** open the folder in File Explorer, click the address bar at the top, type `cmd` and press Enter. A black Command Prompt window opens in that folder.
- **macOS:** open **Terminal** (Cmd+Space, type *Terminal*, Enter), type `cd ` (with a space after it), drag the folder from Finder into the window, then press Enter.
- **Linux:** right-click inside the folder in your file manager and choose **Open in Terminal**.

## 2. Install and first run

### Step 1: Get the code

**Without Git (easiest):**

1. On this project's GitHub page, click the green **Code** button → **Download ZIP**.
2. Find the ZIP in your Downloads folder and extract it. On Windows: right-click → **Extract All** → **Extract**. Don't run anything from inside the ZIP without extracting it first.
3. You get a folder named `DocTrace-main`. Open it until you see `start.bat`, `start.sh` and `README.md`: this is the project folder (called `DocTrace` in this guide). You can rename it and move it anywhere, e.g. to Documents.

**With Git:** in a terminal:

```bash
git clone https://github.com/AshishIsaac/DocTrace.git
cd DocTrace
```

### Step 2: Add your documents

Copy your files into the `data/` folder inside the project folder, in any folder structure you like. The folder names are shown in the results and help the search:

```
data/
├── Semester 3/
│   ├── DBMS/Unit 2 - Normalization.pdf
│   └── OS/Scheduling slides.pptx
└── Semester 4/
    └── Networks/CN lecture 5.pptx
```

**Want your files to stay where they are?** Skip this step and point the app at that folder instead:

1. In the project folder, make a copy of `.env.example` and name the copy `.env`. (Windows may hide the extension: the result must be called exactly `.env`, not `.env.txt`. In a Command Prompt opened in the folder, `copy .env.example .env` does it reliably.)
2. Open `.env` in a text editor and change the line `DOCTRACE_DATA_DIR=data` to your folder, using forward slashes, e.g. `DOCTRACE_DATA_DIR=D:/College Notes` or `DOCTRACE_DATA_DIR=/Users/me/Documents/Notes`. Save.

You can also do this later; see [Settings](#4-settings-env).

### Step 3: Run the start script

| Windows | macOS / Linux |
|---|---|
| Double-click **`start.bat`** in the project folder. If Windows shows *"Windows protected your PC"*, click **More info → Run anyway** | [Open a terminal in the project folder](#1-what-you-need) and run `bash start.sh` |

**The first run sets everything up. It takes about 5-15 minutes, depending on your internet speed.** Keep the window open. It:

1. **finds Python.** On Windows, if none is installed, it asks *"Install Python 3.12 now with winget [Y,N]?"*: press **Y** (no Enter needed). If Windows then asks *"Do you want to allow this app to make changes?"*, click **Yes**. If it still says Python wasn't found afterwards, close the window and double-click `start.bat` again.
2. creates a private environment in `.venv/`, so nothing is installed system-wide except the optional extras you agree to
3. installs PyTorch and the other packages. Many lines scroll by; that's normal.
4. creates your settings file `.env` (unless you already made one) and the `data/` folder
5. **asks you a few yes/no questions.** Type `y` and press Enter for yes, or just press Enter for no:
   - *"NVIDIA GPU found. Install the GPU build of PyTorch?"*: only appears if you have an NVIDIA GPU. Say **no** unless you have thousands of documents (see [GPU](#gpu))
   - *"Install Tesseract OCR (reads images and scanned PDFs)?"*: say **yes** if you have scanned PDFs or photos of notes (see [OCR](#ocr-for-images-and-scanned-pdfs))
   - *"Install Ollama (writes answers from your files; ...)?"*: say **yes** if you want written answers, not just search results (see [AI answers](#ai-answers-with-ollama))
   - *"Download the Ollama model now (about 2 GB)?"*: only appears once Ollama is installed. You can also do this later with one click in the app

   What saying yes involves:
   - **Windows:** an installer runs, and Windows may ask *"Do you want to allow this app to make changes?"*: click **Yes**.
   - **Linux:** you're asked for your password (`[sudo] password for ...`). Nothing appears while you type it; that's normal, so just type it and press Enter.
   - **macOS:** this needs [Homebrew](https://brew.sh). Without it you'll see *"Homebrew is not installed"* and the extra is skipped. Install it later as described in [Optional extras](#5-optional-extras).
6. **downloads the search model and runs a health check.** Lines marked `[  OK ]` are fine, and `[WARN ]` lines are optional items, not errors. On a first run you'll typically see warnings like *"No index yet"*, *"No supported files"* or *"Tesseract not found"*. Only `[FAIL ]` lines need fixing; each comes with a `->` line telling you how.

Setup ends with a *"Setup complete."* message that tells you to add your files and run the start script. When setup was started by `start.bat` / `start.sh`, you don't need to do anything: it carries on by itself. It then, on this run and every later run:

- **updates the index.** It reads your documents, and later runs only process new, changed or deleted files. The first time this takes from under a minute to an hour or more, depending on how many files you have. A progress bar is shown, and you can stop it with `Ctrl+C` at any time: finished files are kept, the app opens with what is indexed so far, and the next run continues. It ends with a line like `[OK] Index updated: 120 files / 3450 passages searchable ...` (or `[OK] No new data` when nothing changed). If your data folder is still empty, it says *"Nothing to index yet"*: add files, then click **Update index** in the app. If indexing fails, the message says why, and the app still opens with the existing index.
- **opens the search page** in your browser at <http://127.0.0.1:7860>.

If the browser doesn't open by itself, copy the address printed in the window (`Running on local URL: http://127.0.0.1:7860`) into your browser. If port 7860 is taken, another port is used and printed instead.

### Stopping and starting again

- **To stop:** close the window (Windows), or press `Ctrl+C` in the terminal (macOS/Linux). Closing the browser tab alone doesn't stop the app.
- **To use it again later:** run `start.bat` / `bash start.sh` again. Setup is skipped and it opens in seconds, after picking up any file changes.
- **Or, once setup is done, use `python run.py`** (`python3 run.py` on macOS/Linux) in a terminal in the project folder. You don't need to activate anything. It first checks whether files were added, changed or deleted since the last run. If nothing changed, it says *"No new data: all N files are already indexed"* and opens the app right away. Otherwise it lists the changes (`+` new, `~` changed, `-` deleted), updates the index, and then opens the app.
- **Don't want a browser tab opened each time?** Run `start.bat --no-browser` / `bash start.sh --no-browser`, then open the printed address yourself.
- If the app started Ollama for you, Ollama keeps running in the background after you close the app (it uses memory, but no CPU when idle). To stop it: on Windows, right-click the Ollama icon in the taskbar's notification area → **Quit**, or if there's no icon, end `ollama.exe` in Task Manager. On macOS, click the Ollama icon in the menu bar → **Quit**, or run `pkill ollama`. On Linux, run `sudo systemctl stop ollama`.

## 3. Using the app

- **Search:** type a question (*"conditions for deadlock"*) or keywords (*"3NF"*) and press Enter or click **Search**. Each result card shows:
  - the file name and its folder path, so you know exactly where it lives
  - the page, slide, sheet or section of each match
  - the matching text with your words highlighted
  - how it matched: *semantic* (similar meaning, with a % score), *keyword* (exact words), or both
- **Search in folder:** limit the search to one folder, such as one semester or subject.
- **Files to show:** how many files to list (1-25).
- **Open file / Show in folder:** pick a result in the **Result file** box under the results, then click **Open file** to open it in its normal program, or **Show in folder** to open its folder. (These buttons only appear when the app runs on your own computer.)
- **Generate an answer (Ollama):** when ticked, each search also writes an answer with `[1]`-style citations pointing to the results. It's **ticked automatically when Ollama is ready**; untick it if you only want search results (answers take longer). The small text under the checkbox tells you whether Ollama is ready and, if not, why. If the model isn't downloaded yet, a **Download the llama3.2 model** button appears. Click it once: progress (`Downloading ... 45% of 2.0 GB`) appears **at the very bottom of the page**, and when it says *"is ready"* the checkbox is ticked for you.
- **Update index:** after you add, change or delete files in your data folder, click it. Only what changed is processed. To do this automatically every few minutes while the app is open, set `DOCTRACE_WATCH_MINUTES=10` in `.env`.
- **Index status:** click this bar to expand it (it's open by itself only while nothing is indexed). The **Log** box shows the progress of updates run from the page in this session; it starts empty each time you open the app. The table lists every file that produced no searchable text, with the reason (unreadable, empty, scanned without OCR, ...).
- **Rebuild from scratch** (inside Index status): re-reads every file. You only need it after installing OCR, after changing the chunk settings, or if something looks wrong.
- Messages from **Open file**, **Show in folder** and the model download appear in a line at the bottom of the page.

## 4. Settings (`.env`)

All settings live in the `.env` file in the `DocTrace` folder. The first run creates it from [.env.example](.env.example), which explains every option. Every setting is optional.

**To change a setting:**

1. Open `.env` in any text editor (Notepad, TextEdit, VS Code, ...). On macOS and Linux the file is hidden in Finder and file managers, so press `Cmd+Shift+.` (macOS) or `Ctrl+H` (Linux) to see it, or run `open -e .env` (macOS).
2. Change the value after the `=`, for example `DOCTRACE_DATA_DIR=D:/College Notes`. Use forward slashes `/` in paths, even on Windows. Don't put quotes around values.
3. Save the file, **close the app and start it again**. Settings are read only at startup.

| Variable | Default | Meaning |
|---|---|---|
| `DOCTRACE_DATA_DIR` | `data` | Folder to index. Relative paths are relative to the `DocTrace` folder. Changing it removes the old folder's files from the index |
| `DOCTRACE_INDEX_DIR` | `vector_db` | Where the index is stored |
| `DOCTRACE_EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Search model. Changing it re-indexes everything. For non-English documents use `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `DOCTRACE_CHUNK_SIZE` / `DOCTRACE_CHUNK_OVERLAP` | `1000` / `150` | Passage length and overlap in characters. Changes apply after **Rebuild from scratch** |
| `DOCTRACE_MAX_FILE_MB` | `200` | Skip files larger than this |
| `DOCTRACE_WORKERS` | CPU count - 1 (max 8) | Files read in parallel while indexing |
| `DOCTRACE_OCR` | `auto` | `auto` (use OCR if Tesseract is installed), `on` (fail if it's missing) or `off` |
| `TESSERACT_CMD` | empty | Full path to `tesseract` if it isn't found automatically |
| `DOCTRACE_LLM` | `auto` | `auto` / `ollama` (answers when Ollama is available) or `none` (search only) |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `llama3.2` | Ollama server and model |
| `OLLAMA_AUTOSTART` | `1` | Start Ollama in the background automatically when needed |
| `DOCTRACE_HOST` / `DOCTRACE_PORT` | `127.0.0.1` / `7860` | Web page address. See [other devices](#using-it-from-your-phone-or-another-computer) |
| `DOCTRACE_ALLOW_OPEN` | `1` | Show the Open file / Show in folder buttons (only on your own computer) |
| `DOCTRACE_WATCH_MINUTES` | `0` | Re-scan the data folder every N minutes while the app runs (`0` = only when you click **Update index**) |
| `GDRIVE_FOLDER_ID` / `GDRIVE_CREDENTIALS` | empty / `service_account.json` | Google Drive folder to index and its key file. See [Google Drive](#google-drive-as-a-source) |

## 5. Optional extras

Each of these can be added at any time, not only during the first setup.

### AI answers with Ollama

Without an LLM the app is a search engine. To also get written answers:

1. **Install Ollama:**
   - Windows: `winget install Ollama.Ollama`, or the installer from [ollama.com/download](https://ollama.com/download)
   - macOS: `brew install --cask ollama`, or the app from [ollama.com/download](https://ollama.com/download)
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh` (asks for your password)
2. **Restart the app** (`start.bat` / `bash start.sh`). Ollama is started in the background automatically.
3. **Download the model:** click **Download the llama3.2 model** in the app (about 2 GB, once). Or, with the environment activated ([how](#6-terminal-commands)), run `python doctor.py --pull-ollama-model`.
4. Tick **Generate an answer (Ollama)** and search.

The default model `llama3.2` (3B parameters, ~2 GB) runs on most laptops with 8 GB of RAM. For better answers on a machine with 16 GB+ RAM or a GPU, set `OLLAMA_MODEL=llama3.1:8b`, `qwen2.5:7b` or `mistral` in `.env`, restart the app and click the download button again. Answers are generated on your computer, so the first one can take 10-60 seconds on a laptop.

### OCR for images and scanned PDFs

Without OCR, photos and scanned PDFs (pages that are pictures of text) can't be searched. They're listed under **Index status** instead. To read them, install the free Tesseract program:

- **Windows:** `winget install UB-Mannheim.TesseractOCR`, or the installer from [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki). The default install location is detected automatically. If you installed it somewhere else, set `TESSERACT_CMD` in `.env`, e.g. `TESSERACT_CMD=D:/Tools/Tesseract-OCR/tesseract.exe`.
- **macOS:** `brew install tesseract`
- **Ubuntu/Debian:** `sudo apt install tesseract-ocr`. Fedora: `sudo dnf install tesseract`

Then restart the app and click **Rebuild from scratch** (or run `python ingest.py --rebuild`) so files that were already indexed get read again with OCR. OCR is set up for English text, and it's slower than normal reading, so a large scanned collection can take a while.

### GPU

By default setup installs the small CPU build of PyTorch (~200 MB). If it finds an NVIDIA GPU, it asks whether you want the GPU build instead (~2.5 GB). A GPU only speeds up indexing very large collections; searching is fast either way. To switch later, delete the `.venv/` folder and run `setup.bat --gpu` / `bash setup.sh --gpu` (or `--cpu`). On a Mac, Apple GPU support is included automatically.

### Google Drive as a source

The app can also index a Google Drive folder. It reads Drive through a *service account*: a robot Google account you create once and share your folder with. It gets read-only access to just the folders you share with it.

**1. Install Drive support.** Run `setup.bat --gdrive` / `bash setup.sh --gdrive`, or, with the environment activated, `pip install -r requirements-gdrive.txt`.

**2. Create the service account and its key** (free, about 5 minutes):

1. Open [console.cloud.google.com](https://console.cloud.google.com) and sign in with any Google account.
2. Create a project: click the project picker at the top → **New project** → give it any name → **Create**, then make sure it's selected.
3. Enable the Drive API: open [the Google Drive API page](https://console.cloud.google.com/apis/library/drive.googleapis.com) → **Enable**.
4. Create the service account: go to **IAM & Admin → Service accounts** → **Create service account** → enter a name (e.g. `doctrace-drive-reader`) → **Create and continue** → skip the optional role and user steps → **Done**.
5. Create its key: click the new service account → **Keys** tab → **Add key → Create new key** → **JSON** → **Create**. A `.json` file downloads.
6. Rename that file to `service_account.json` and move it into the `DocTrace` folder. Treat it like a password: it's git-ignored, so **never commit or share it**.

**3. Share your Drive folder with it.** On the service account's page, copy its e-mail address (it looks like `doctrace-drive-reader@your-project.iam.gserviceaccount.com`). In Google Drive, right-click your folder → **Share** → paste that address → role **Viewer** → **Send**.

**4. Tell the app which folder to index.** Open the folder in Drive in your browser. The ID is the last part of the address: in `https://drive.google.com/drive/folders/1AbCdEfGh...` it's `1AbCdEfGh...`. Put it in `.env`: `GDRIVE_FOLDER_ID=1AbCdEfGh...`.

**5. Index it.** Activate the environment ([how](#6-terminal-commands)) and run `python ingest.py --gdrive` (local folder + Drive) or `python ingest.py --gdrive --no-local` (Drive only). Then start the app as usual.

Google Docs, Slides and Sheets are exported automatically, and sub-folders and shortcuts are followed. Drive results are tagged *Google Drive* and link to the file in Drive.

Good to know:

- The start script and the **Update index** button refresh only the local folder. Drive results stay searchable, but to pick up changes in Drive, re-run `python ingest.py --gdrive`.
- **Rebuild from scratch** clears Drive results too. Restore them with `python ingest.py --gdrive --rebuild`.

### Docker

An alternative to the start script if you already use Docker. It includes Tesseract and runs Ollama in a second container.

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS), or Docker Engine with the Compose plugin (Linux).
2. Put your files in `data/`, then in the `DocTrace` folder run:

```bash
docker compose up --build
```

3. The first build downloads several GB and takes a while. On the first start the app indexes your files before the page comes up. When the log shows `Running on local URL`, open <http://localhost:7860>.
4. For AI answers, click **Download the llama3.2 model** in the app once.

| Task | Command |
|---|---|
| Run in the background | `docker compose up -d --build`, then follow the log with `docker compose logs -f app` |
| Stop | `Ctrl+C`, or `docker compose down` if it runs in the background |
| Index another folder (macOS/Linux) | `DATA_PATH="/path/to/notes" docker compose up` |
| Index another folder (Windows PowerShell) | `$env:DATA_PATH="D:\College Notes"; docker compose up` |
| Use another port | `DOCTRACE_PORT=8080 docker compose up` (PowerShell: `$env:DOCTRACE_PORT="8080"; docker compose up`), then open <http://localhost:8080>. The log still says 7860, which is the port inside the container |
| Delete the index and downloaded model | `docker compose down -v` |

**Settings in Docker:** only `DATA_PATH`, `DOCTRACE_PORT`, `OLLAMA_MODEL` and `DOCTRACE_WATCH_MINUTES` are used, from your terminal or from `.env`. All other `.env` settings (search model, OCR, chunk size, ...) don't apply inside the container. To change them, add them under `environment:` for the `app` service in `docker-compose.yml`, e.g. `DOCTRACE_EMBED_MODEL: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, then run `docker compose up --build` again.

The data folder is mounted read-only and re-scanned every 10 minutes (or every `DOCTRACE_WATCH_MINUTES` from `.env`; the `.env` that the start script creates sets it to `0`, which turns the re-scan off, so delete that line or set a number to keep it). Open file / Show in folder are disabled, because the app runs inside the container. To use an NVIDIA GPU for Ollama, uncomment the `deploy:` block in `docker-compose.yml`.

### Using it from your phone or another computer

- **Same Wi-Fi network:** set `DOCTRACE_HOST=0.0.0.0` in `.env` and restart the app. On the other device, open `http://<your-computer's-IP>:7860`. Find the IP with `ipconfig` (Windows, "IPv4 Address") or `ipconfig getifaddr en0` (macOS). Allow the connection if your firewall asks. Anyone on that network can then search your files.
- **Anywhere, temporarily:** run `python search_app.py --share` (environment activated). It prints a public `https://....gradio.live` link. **Anyone with that link can search your documents**, so only share it with people you trust. It stops working when you close the app.

Open file / Show in folder are hidden in both modes.

## 6. Terminal commands

The start script handles everything, so you never *need* the terminal. To run commands yourself, open a terminal in the `DocTrace` folder and **activate the environment first**:

| Windows (Command Prompt) | Windows (PowerShell) | macOS / Linux |
|---|---|---|
| `.venv\Scripts\activate` | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |

Your prompt then starts with `(.venv)`. Without this step, commands fail with `ModuleNotFoundError`. If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt.

| Command | What it does |
|---|---|
| `start.bat` / `bash start.sh` | Set up if needed, update the index, open the app |
| `python run.py` | After setup: check for new/changed/deleted files, index them only if there are any, then open the app. Uses `.venv` automatically, so no activation is needed. Accepts the `search_app.py` options, e.g. `python run.py --no-browser` |
| `setup.bat` / `bash setup.sh` | Setup only. Options: `--yes` (install all extras), `--no-extras`, `--cpu`, `--gpu`, `--gdrive` |
| `python ingest.py` | Update the index (incremental; safe to stop with `Ctrl+C`, and the next run continues) |
| `python ingest.py --rebuild` | Re-index everything from scratch |
| `python ingest.py --gdrive` / `--gdrive --no-local` | Also index / only index the Google Drive folder |
| `python ingest.py --data-dir PATH` | Index a different folder once. To switch folders for good, set `DOCTRACE_DATA_DIR` in `.env` instead: the start script and **Update index** use that setting and drop entries from any other folder |
| `python search_app.py` | Open the app. Options: `--no-browser`, `--share` |
| `python search_app.py -q "question"` | Search in the terminal and print the results (and an answer, if Ollama is ready). `-k 10` shows 10 files (default 5) |
| `python doctor.py` | Check the installation and print a fix for anything missing |
| `python doctor.py --pull-ollama-model` | Download the Ollama model set in `.env` |
| `python doctor.py --download-model` | Download the search model now (setup does this for you) |
| `PYTHON=python3.12 bash setup.sh` | macOS/Linux: use a specific Python for setup, if you have several |

## 7. Updating, moving and uninstalling

**Updating to a newer version:**

```bash
git pull            # without Git: download the new ZIP, extract it, and copy data/, vector_db/, .env
                    # (and service_account.json if you use Drive) from the old folder into the new one
setup.bat           # macOS/Linux: bash setup.sh   (installs any new packages)
start.bat           # macOS/Linux: bash start.sh
```

Your documents, `.env` and index are kept. If something behaves oddly after an update, click **Rebuild from scratch** once.

**Moving the folder:** you can move or rename the `DocTrace` folder. Afterwards, delete the `.venv/` folder and run the start script again: the environment is recreated, and the index is rebuilt because the data folder's location changed.

**Uninstalling:** delete the `DocTrace` folder. That removes the app, its environment and the index. Your documents are only touched if they're inside its `data/` folder. Optionally also delete:

- the search model cache (~90 MB): `%USERPROFILE%\.cache\huggingface` (Windows) or `~/.cache/huggingface` (macOS/Linux). Other Python AI tools may share this cache.
- Ollama and its models: uninstall Ollama like any other program. Its models are stored in `%USERPROFILE%\.ollama` or `~/.ollama`.
- Tesseract: uninstall it like any other program.

## 8. Troubleshooting

First, run the health check. It tests Python, packages, GPU, the search model, Tesseract, Ollama, your data folder and the index, and prints the exact fix for anything missing:

```bash
python doctor.py      # activate the environment first (see Terminal commands)
```

| Problem | Fix |
|---|---|
| Setup stopped with *"Setup failed at: ... pip install ..."* | Check your internet connection and run the start script again; it continues where it stopped. On Windows, antivirus briefly locking files can cause this too, and running it again fixes it |
| Setup or the model download fails on a college/office network (*"Could not download ..."*, connection or SSL errors) | The network probably needs a proxy. Ask your IT department for its address, then in a terminal in the project folder run `set HTTPS_PROXY=http://proxy.example.com:8080` (Windows Command Prompt) or `export HTTPS_PROXY=http://proxy.example.com:8080` (macOS/Linux), followed by `start.bat` / `bash start.sh` in the same window. Or use a different network (e.g. a phone hotspot) for the first run |
| `Error: ... in .env ...`, e.g. *"DOCTRACE_PORT='abc' in .env is not a valid number"*, *"DOCTRACE_OCR must be auto, on or off"*, *"DOCTRACE_CHUNK_OVERLAP must be smaller than DOCTRACE_CHUNK_SIZE"* | A value in `.env` is mistyped. Fix that line, or delete it to use the default, then start again |
| *"DOCTRACE_OCR=on but tesseract was not found"* | Install Tesseract ([OCR](#ocr-for-images-and-scanned-pdfs)), or set `DOCTRACE_OCR=auto` in `.env` |
| "Python 3.10 or newer was not found" | Install Python as described in [What you need](#1-what-you-need), then run the start script again. On Windows, open a new window after installing |
| "... is missing the venv module" (Linux) | `sudo apt install python3-venv`, then run `bash start.sh` again |
| The browser doesn't open | Copy the `http://127.0.0.1:...` address from the window into your browser |
| "Nothing is indexed yet" | Put files in `data/` (or set `DOCTRACE_DATA_DIR`) and click **Update index** |
| "Data folder not found" | The folder in `DOCTRACE_DATA_DIR` doesn't exist. Check the spelling in `.env`, using forward slashes `/` |
| A file is missing from the results | Open **Index status**: files that couldn't be read are listed there with the reason. Also check [Supported files](#9-supported-files): old `.doc`/`.ppt`/`.xls`, hidden files and files over 200 MB are skipped |
| Scanned PDFs / images aren't found | Install Tesseract ([OCR](#ocr-for-images-and-scanned-pdfs)), restart the app, click **Rebuild from scratch** |
| Results are poor for non-English documents | Use the multilingual model: `DOCTRACE_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (re-indexes automatically) |
| "Install Ollama ..." / "Ollama is not running" | Install Ollama ([AI answers](#ai-answers-with-ollama)), or start the Ollama app / run `ollama serve` |
| "The model ... is not downloaded yet" | Click the **Download ... model** button in the app |
| Answers are very slow | Normal for a laptop CPU. Use a smaller model, e.g. `OLLAMA_MODEL=llama3.2:1b`, or set `DOCTRACE_LLM=none` for search only |
| *"Another indexing run is already in progress"* (terminal) or *"An update is already running ..."* (app) | Wait for it to finish, or close the other window running `ingest.py` / the app |
| *"LLM error: ..."* under the answer, e.g. a timeout or *"model requires more system memory"* | Your computer is short on memory or too slow for the model. Close other programs, or use a smaller model: set `OLLAMA_MODEL=llama3.2:1b` in `.env`, restart the app and click **Download the llama3.2:1b model** |
| Port 7860 in use | Nothing to do: the next free port is used and printed in the window |
| A change in `.env` has no effect | Close the app and start it again; settings are read only at startup |
| `ModuleNotFoundError` when running a command | Activate the environment first ([Terminal commands](#6-terminal-commands)). If it says `No module named 'google'` while using `--gdrive`, install Drive support (step 1 under [Google Drive](#google-drive-as-a-source)) |
| Google Drive: *"Google Drive indexing needs GDRIVE_FOLDER_ID in .env"* | Add `GDRIVE_FOLDER_ID=...` to `.env` (step 4 under [Google Drive](#google-drive-as-a-source)) |
| Google Drive: "Drive credentials not found" | `service_account.json` must be in the `DocTrace` folder (or set `GDRIVE_CREDENTIALS` to its path) |
| Google Drive: 0 files found | Share the folder with the service account's e-mail address, and check `GDRIVE_FOLDER_ID` is the ID of that folder |
| Google Drive: a long error ending in `HttpError 403` with *"accessNotConfigured"* or *"Drive API has not been used in project ..."* | Enable the Drive API for your project (step 2.3 under [Google Drive](#google-drive-as-a-source)), wait a minute, run it again |
| Start completely fresh | Delete the `vector_db/` folder, or run `python ingest.py --rebuild` |
| Broken installation | Delete the `.venv/` folder and run the start script again |

## 9. Supported files

| Type | Extensions | Location shown |
|---|---|---|
| PDF | `.pdf` | page |
| Word | `.docx` | heading / section, tables |
| PowerPoint | `.pptx` | slide (incl. speaker notes) |
| Excel | `.xlsx`, `.xlsm` | sheet |
| Web pages | `.html`, `.htm` | file |
| Notebooks | `.ipynb` | cell |
| Text & data | `.txt .md .markdown .rst .csv .tsv .json .yaml .yml .xml .tex .log .ini .cfg .toml` | file |
| Code | `.py .js .ts .jsx .tsx .java .c .h .cpp .hpp .cs .go .rs .rb .php .kt .swift .m .r .sql .sh .bat .ps1 .css .scss` | file |
| Images (needs OCR) | `.png .jpg .jpeg .tif .tiff .bmp .webp` | file |
| Scanned PDF pages (needs OCR) | `.pdf` | page |

**Skipped automatically:**

- old binary Office formats (`.doc`, `.ppt`, `.xls`). Open them in Word/PowerPoint/Excel and use **Save as** `.docx`/`.pptx`/`.xlsx`.
- hidden files and folders (names starting with `.`), Office lock files (`~$...`), and system folders such as `node_modules`, `.git` and `$RECYCLE.BIN`
- empty files, and files larger than `DOCTRACE_MAX_FILE_MB` (200 MB)
- password-protected or corrupt files. These are listed under **Index status**

## 10. How it works

```
ingest.py / "Update index"
  scan folder ──► extract text per page/slide/sheet ──► split into overlapping chunks
             ──► embed (sentence-transformers) ──► vector_db/doctrace.sqlite  (text, vectors, keyword index)
                                                    vector_db/index.faiss (vector index)
search_app.py
  question ──► semantic search (FAISS) + keyword search (SQLite FTS5)
           ──► merge rankings (reciprocal rank fusion) ──► group by file ──► results (+ optional Ollama answer)
```

The folder path is embedded together with each chunk, so folder names such as `Semester 3/DBMS` help the search too. Files are tracked by modification time and size, so re-runs only touch what changed.

## Project structure

```
start.bat / start.sh     one-click launcher (sets up on first use)
run.py                   launcher: index only if files changed, then open the app
setup.bat / setup.sh     one-time setup (calls scripts/bootstrap.py)
ingest.py                build / update the index
search_app.py            web UI and terminal search
doctor.py                installation check
doctrace/
  config.py              settings from .env
  indexer.py             incremental indexing pipeline
  local.py, gdrive.py    file sources
  extract.py, chunk.py   text extraction and chunking
  embed.py               embedding model
  store.py               SQLite + FAISS storage
  search.py              hybrid retrieval
  llm.py                 Ollama integration
tests/                   pytest suite (runs in seconds, no model download)
data/                    your documents (git-ignored)
vector_db/               generated index (git-ignored)
```

## Development

```bash
pip install -r requirements-dev.txt      # with the environment activated
pytest          # tests use a fake embedder, so they're fast and offline
ruff check .
```

GitHub Actions runs both on Windows, macOS and Linux for every push (`.github/workflows/ci.yml`).

## License

[MIT](LICENSE)
