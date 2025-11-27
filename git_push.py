# git_push.py
import os, threading, subprocess, shlex, logging, time, stat

logger = logging.getLogger("git_push")
logger.setLevel(logging.INFO)

# Config từ env
ENABLE = os.environ.get("ENABLE_GIT_PUSH", "false").lower() == "true"
GIT_SSH_KEY = os.environ.get("GIT_SSH_KEY")  # private key content
GIT_REPO = os.environ.get("GIT_REPO", "git@github.com:OWNER/REPO.git")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "render-bot")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "render-bot@example.com")

SSH_KEY_PATH = "/tmp/id_render_deploy"   # temp path inside container
KNOWN_HOSTS = "/tmp/known_hosts_render"

def setup_ssh():
    if not ENABLE:
        logger.info("Git push disabled by ENABLE_GIT_PUSH")
        return False
    if not GIT_SSH_KEY:
        logger.warning("GIT_SSH_KEY not set; skipping SSH setup")
        return False
    # write key
    with open(SSH_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(GIT_SSH_KEY)
    os.chmod(SSH_KEY_PATH, 0o600)
    # try ssh-keyscan
    try:
        out = subprocess.check_output(["ssh-keyscan", "github.com"], stderr=subprocess.DEVNULL)
        with open(KNOWN_HOSTS, "wb") as kh:
            kh.write(out)
    except Exception:
        logger.warning("ssh-keyscan not available; continuing without known_hosts")
    # set GIT_SSH_COMMAND
    os.environ["GIT_SSH_COMMAND"] = f"ssh -i {shlex.quote(SSH_KEY_PATH)} -o UserKnownHostsFile={shlex.quote(KNOWN_HOSTS)} -o StrictHostKeyChecking=yes"
    logger.info("SSH setup done")
    return True

def _run(cmd, cwd=None, check=True):
    logger.info("CMD: %s", cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    logger.info("OUT: %s", r.stdout.strip())
    if r.returncode != 0:
        logger.error("ERR: %s", r.stderr.strip())
        if check:
            raise RuntimeError(r.stderr.strip())
    return r

def git_push_files(local_files, commit_message="Auto update from Render"):
    if not ENABLE:
        logger.info("git_push_files skipped: disabled")
        return {"status":"disabled"}
    if not setup_ssh():
        return {"status":"no_ssh"}
    attempt = 0
    max_retries = 2
    while attempt <= max_retries:
        attempt += 1
        try:
            _run(f'git config user.name "{GIT_USER_NAME}"')
            _run(f'git config user.email "{GIT_USER_EMAIL}"')
            _run(f'git remote set-url origin {GIT_REPO}')
            _run('git fetch origin')
            _run(f'git checkout {GIT_BRANCH}')
            files_str = " ".join(shlex.quote(f) for f in local_files)
            _run(f'git add {files_str}')
            status = subprocess.run('git status --porcelain', shell=True, stdout=subprocess.PIPE, text=True)
            if not status.stdout.strip():
                logger.info("No changes to commit")
                return {"status":"no_changes"}
            _run(f'git commit -m "{commit_message}"')
            # rebase/pull to reduce push rejects
            try:
                _run(f'git pull --rebase origin {GIT_BRANCH}', check=False)
            except Exception:
                logger.warning("git pull --rebase failed; continuing")
            _run(f'git push origin {GIT_BRANCH}')
            logger.info("Push OK")
            return {"status":"pushed"}
        except Exception as e:
            logger.exception("Push attempt %d failed", attempt)
            time.sleep(1 + attempt)
            if attempt > max_retries:
                return {"status":"failed", "error": str(e)}

def push_async(local_files, commit_message="Auto update from Render"):
    def worker():
        try:
            res = git_push_files(local_files, commit_message)
            logger.info("Background push result: %s", res)
        except Exception:
            logger.exception("Background push exception")
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t