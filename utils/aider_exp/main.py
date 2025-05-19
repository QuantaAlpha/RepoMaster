import sys
import argparse

try:
    import git

    ANY_GIT_ERROR = [
        git.exc.ODBError,
        git.exc.GitError,
        git.exc.InvalidGitRepositoryError,
        git.exc.GitCommandNotFound,
    ]
except ImportError:
    git = None
    ANY_GIT_ERROR = []

from pathlib import Path
from utils.io import read_text
from utils.utils import safe_abs_path
from repo import Repo
from repomap import RepoMap

def make_new_repo(git_root):
    try:
        repo = git.Repo.init(git_root)
        check_gitignore(git_root, False)
    except ANY_GIT_ERROR as err: 
        print(f"Unable to create git repo in {git_root}")
        print(str(err))
        return

    print(f"Git repository created in {git_root}")
    return repo


def setup_git(git_root):
    if git is None:
        return

    try:
        cwd = Path.cwd()
    except OSError:
        cwd = None

    repo = None

    if git_root:
        try:
            repo = git.Repo(git_root)
        except ANY_GIT_ERROR:
            pass
    elif cwd == Path.home():
        print(
            "You should probably run in your project's directory, not your home dir."
        )
        return
    elif cwd:
        git_root = str(cwd.resolve())
        repo = make_new_repo(git_root)

    if not repo:
        return

    try:
        user_name = repo.git.config("--get", "user.name") or None
    except git.exc.GitCommandError:
        user_name = None

    try:
        user_email = repo.git.config("--get", "user.email") or None
    except git.exc.GitCommandError:
        user_email = None

    if user_name and user_email:
        return repo.working_tree_dir

    with repo.config_writer() as git_config:
        if not user_name:
            git_config.set_value("user", "name", "Your Name")
            print('Update git name with: git config user.name "Your Name"')
        if not user_email:
            git_config.set_value("user", "email", "you@example.com")
            print('Update git email with: git config user.email "you@example.com"')

    return repo.working_tree_dir


def check_gitignore(git_root, ask=True):
    if not git_root:
        return

    try:
        repo = git.Repo(git_root)
        patterns_to_add = []

        env_path = Path(git_root) / ".env"
        if env_path.exists() and not repo.ignored(".env"):
            patterns_to_add.append(".env")

        if not patterns_to_add:
            return

        gitignore_file = Path(git_root) / ".gitignore"
        if gitignore_file.exists():
            try:
                content = read_text(gitignore_file)
                if content is None:
                    return
                if not content.endswith("\n"):
                    content += "\n"
            except OSError as e:
                print(f"Error when trying to read {gitignore_file}: {e}")
                return
        else:
            content = ""
    except ANY_GIT_ERROR:
        return

    # if ask:
    #     io.tool_output("You can skip this check with --no-gitignore")
    #     if not io.confirm_ask(f"Add {', '.join(patterns_to_add)} to .gitignore (recommended)?"):
    #         return

    # content += "\n".join(patterns_to_add) + "\n"

    # try:
    #     io.write_text(gitignore_file, content)
    #     io.tool_output(f"Added {', '.join(patterns_to_add)} to .gitignore")
    # except OSError as e:
    #     io.tool_error(f"Error when trying to write to {gitignore_file}: {e}")
    #     io.tool_output(
    #         "Try running with appropriate permissions or manually add these patterns to .gitignore:"
    #     )
    #     for pattern in patterns_to_add:
    #         io.tool_output(f"  {pattern}")


def sanity_check_repo(repo):
    if not repo:
        return True

    if not repo.repo.working_tree_dir:
        print("The git repo does not seem to have a working tree?")
        return False

    bad_ver = False
    try:
        repo.get_tracked_files()
        if not repo.git_repo_error: 
            return True
        error_msg = str(repo.git_repo_error)
    except UnicodeDecodeError as exc:
        error_msg = (
            "Failed to read the Git repository. This issue is likely caused by a path encoded "
            f'in a format different from the expected encoding "{sys.getfilesystemencoding()}".\n'
            f"Internal error: {str(exc)}"
        )
    except ANY_GIT_ERROR as exc:
        error_msg = str(exc)
        bad_ver = "version in (1, 2)" in error_msg
    except AssertionError as exc:
        error_msg = str(exc)
        bad_ver = True

    if bad_ver:
        print("only works with git repos with version number 1 or 2.")
        print("You may be able to convert your repo: git update-index --index-version=2")
        print("Or to proceed without using git.")
        return False

    print("Unable to read git repository, it may be corrupt?")
    print(error_msg)
    return False

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sanity-check-repo", action="store_true")
    parser.add_argument("--map-tokens", type=int, default=409600)
    args = parser.parse_args()

    git_root = setup_git("/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/fish-speech")
    check_gitignore(git_root, False)

    repo = Repo(git_root)
    if not args.skip_sanity_check_repo:
        if not sanity_check_repo(repo):
            print("Repository sanity check failed")
            sys.exit(1)
    print(f"num of tracked files: {len(repo.get_tracked_files())}")
    
    repo_map = RepoMap(map_tokens=args.map_tokens, root=git_root)

    files = sorted(set(repo.get_tracked_files()))
    files = [safe_abs_path(Path(git_root) / file) for file in files]
    import pdb;pdb.set_trace()
    
    # repo_content = repo_map.get_repo_map(set(), files)
    # print(repo_content)
    repo_content = repo_map.get_repo_map(set(), ['/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/fish-speech/tools/sensevoice/vad_utils.py'])
    print(repo_content)
