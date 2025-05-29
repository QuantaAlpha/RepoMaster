import os
import time
from pathlib import Path, PurePosixPath

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

import pathspec

from utils import utils

ANY_GIT_ERROR += [
    OSError,
    IndexError,
    BufferError,
    TypeError,
    ValueError,
    AttributeError,
    AssertionError,
    TimeoutError,
]
ANY_GIT_ERROR = tuple(ANY_GIT_ERROR)


class Repo:
    repo = None
    ignore_file_cache = {}
    git_repo_error = None

    def __init__(
        self,
        git_root,
        subtree_only=False,
        git_commit_verify=True,
    ):
        self.normalized_path = {}
        self.tree_files = {}

        self.subtree_only = subtree_only
        self.git_commit_verify = git_commit_verify
        self.ignore_file_cache = {}

        try:
            repo_path = git.Repo(git_root, search_parent_directories=True).working_dir
            repo_path = utils.safe_abs_path(repo_path)
        except ANY_GIT_ERROR:
            pass

        self.repo = git.Repo(repo_path, odbt=git.GitDB)
        self.root = utils.safe_abs_path(self.repo.working_tree_dir)

    def get_rel_repo_dir(self):
        try:
            return os.path.relpath(self.repo.git_dir, os.getcwd())
        except (ValueError, OSError):
            return self.repo.git_dir
        
    def get_repo_map(self, force_refresh=False):
        if not self.repo_map:
            return

        cur_msg_text = self.get_cur_message_text()
        mentioned_fnames = self.get_file_mentions(cur_msg_text)
        mentioned_idents = self.get_ident_mentions(cur_msg_text)

        mentioned_fnames.update(self.get_ident_filename_matches(mentioned_idents))

        all_abs_files = set(self.get_all_abs_files())
        repo_abs_read_only_fnames = set(self.abs_read_only_fnames) & all_abs_files
        chat_files = set(self.abs_fnames) | repo_abs_read_only_fnames
        other_files = all_abs_files - chat_files

        repo_content = self.repo_map.get_repo_map(
            chat_files,
            other_files,
            mentioned_fnames=mentioned_fnames,
            mentioned_idents=mentioned_idents,
            force_refresh=force_refresh,
        )

        # fall back to global repo map if files in chat are disjoint from rest of repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                all_abs_files,
                mentioned_fnames=mentioned_fnames,
                mentioned_idents=mentioned_idents,
            )

        # fall back to completely unhinted repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                all_abs_files,
            )

        return repo_content

    def get_repo_messages(self):
        repo_messages = []
        repo_content = self.get_repo_map()
        if repo_content:
            repo_messages += [
                dict(role="user", content=repo_content),
                dict(
                    role="assistant",
                    content="Ok, I won't try and edit those files without asking first.",
                ),
            ]
        return repo_messages

    def get_diffs(self, fnames=None):
        # We always want diffs of index and working dir

        current_branch_has_commits = False
        try:
            active_branch = self.repo.active_branch
            try:
                commits = self.repo.iter_commits(active_branch)
                current_branch_has_commits = any(commits)
            except ANY_GIT_ERROR:
                pass
        except (TypeError,) + ANY_GIT_ERROR:
            pass

        if not fnames:
            fnames = []

        diffs = ""
        for fname in fnames:
            if not self.path_in_repo(fname):
                diffs += f"Added {fname}\n"

        try:
            if current_branch_has_commits:
                args = ["HEAD", "--"] + list(fnames)
                diffs += self.repo.git.diff(*args)
                return diffs

            wd_args = ["--"] + list(fnames)
            index_args = ["--cached"] + wd_args

            diffs += self.repo.git.diff(*index_args)
            diffs += self.repo.git.diff(*wd_args)

            return diffs
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to diff: {err}")

    def diff_commits(self, pretty, from_commit, to_commit):
        args = []
        if pretty:
            args += ["--color"]
        else:
            args += ["--color=never"]

        args += [from_commit, to_commit]
        diffs = self.repo.git.diff(*args)

        return diffs

    def get_tracked_files(self):
        if not self.repo:
            return []

        try:
            commit = self.repo.head.commit
        except ValueError:
            commit = None
        except ANY_GIT_ERROR as err:
            self.git_repo_error = err
            print(f"Unable to list files in git repo: {err}")
            print("Is your git repo corrupted?")
            return []

        files = set()
        if commit:
            if commit in self.tree_files:
                files = self.tree_files[commit]
            else:
                try:
                    iterator = commit.tree.traverse()
                    blob = None  # Initialize blob
                    while True:
                        try:
                            blob = next(iterator)
                            if blob.type == "blob":  # blob is a file
                                files.add(blob.path)
                        except IndexError:
                            # Handle potential index error during tree traversal
                            # without relying on potentially unassigned 'blob'
                            print(
                                "GitRepo: Index error encountered while reading git tree object."
                                " Skipping."
                            )
                            continue
                        except StopIteration:
                            break
                except ANY_GIT_ERROR as err:
                    self.git_repo_error = err
                    print(f"Unable to list files in git repo: {err}")
                    print("Is your git repo corrupted?")
                    return []
                files = set(self.normalize_path(path) for path in files)
                self.tree_files[commit] = set(files)

        # Add staged files
        index = self.repo.index
        try:
            staged_files = [path for path, _ in index.entries.keys()]
            files.update(self.normalize_path(path) for path in staged_files)
        except ANY_GIT_ERROR as err:
            print(f"Unable to read staged files: {err}")

        res = [fname for fname in files if not self.ignored_file(fname)]

        return res

    def normalize_path(self, path):
        orig_path = path
        res = self.normalized_path.get(orig_path)
        if res:
            return res

        path = str(Path(PurePosixPath((Path(self.root) / path).relative_to(self.root))))
        self.normalized_path[orig_path] = path
        return path

    def git_ignored_file(self, path):
        if not self.repo:
            return
        try:
            if self.repo.ignored(path):
                return True
        except ANY_GIT_ERROR:
            return False

    def ignored_file(self, fname):
        if fname in self.ignore_file_cache:
            return self.ignore_file_cache[fname]

        result = self.ignored_file_raw(fname)
        self.ignore_file_cache[fname] = result
        return result

    def ignored_file_raw(self, fname):
        if self.subtree_only:
            try:
                fname_path = Path(self.normalize_path(fname))
                cwd_path = Path.cwd().resolve().relative_to(Path(self.root).resolve())
            except ValueError:
                # Issue #1524
                # ValueError: 'C:\\dev\\squid-certbot' is not in the subpath of
                # 'C:\\dev\\squid-certbot'
                # Clearly, fname is not under cwd... so ignore it
                return True

            if cwd_path not in fname_path.parents and fname_path != cwd_path:
                return True

        return False

        # try:
        #     fname = self.normalize_path(fname)
        # except ValueError:
        #     return True

        # return self.aider_ignore_spec.match_file(fname)

    def path_in_repo(self, path):
        if not self.repo:
            return
        if not path:
            return

        tracked_files = set(self.get_tracked_files())
        return self.normalize_path(path) in tracked_files

    def abs_root_path(self, path):
        res = Path(self.root) / path
        return utils.safe_abs_path(res)

    def get_dirty_files(self):
        """
        Returns a list of all files which are dirty (not committed), either staged or in the working
        directory.
        """
        dirty_files = set()

        # Get staged files
        staged_files = self.repo.git.diff("--name-only", "--cached").splitlines()
        dirty_files.update(staged_files)

        # Get unstaged files
        unstaged_files = self.repo.git.diff("--name-only").splitlines()
        dirty_files.update(unstaged_files)

        return list(dirty_files)

    def is_dirty(self, path=None):
        if path and not self.path_in_repo(path):
            return True

        return self.repo.is_dirty(path=path)

    def get_head_commit(self):
        try:
            return self.repo.head.commit
        except (ValueError,) + ANY_GIT_ERROR:
            return None

    def get_head_commit_sha(self, short=False):
        commit = self.get_head_commit()
        if not commit:
            return
        if short:
            return commit.hexsha[:7]
        return commit.hexsha

    def get_head_commit_message(self, default=None):
        commit = self.get_head_commit()
        if not commit:
            return default
        return commit.message
