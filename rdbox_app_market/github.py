#!/usr/bin/env python3
from http.client import InvalidURL
import os
import shutil
import glob
from git import Repo

from logging import getLogger
r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


class GithubRepos(object):

    TOP_DIR = os.path.join('/tmp', '.original.charts')

    def get_dirpath(self):
        return self.repo_dir

    def get_dirpath_with_prefix(self):
        if self.specific_dir_from_top == '':
            return self.get_dirpath()
        else:
            return os.path.join(self.get_dirpath(), self.get_specific_dir_from_top())

    def get_url(self):
        return self.url

    def get_url_of_pages(self):
        url = 'https://{account}.github.io/{repo_name}/{from_top}'.format(
            account=self.get_account_name(),
            repo_name=self.get_repository_name(),
            from_top=self.get_specific_dir_from_top())
        return url

    def get_specific_dir_from_top(self):
        return self.specific_dir_from_top

    def get_account_name(self):
        if self.url.startswith('https'):
            return self.url.split('/')[3]
        if self.url.startswith('git'):
            base = self.url.split(':')[1]
            return base.split('/')[0]

    def get_repository_name(self):
        if self.url.startswith('https'):
            return self.url.split('/')[4].split('.')[0]
        if self.url.startswith('git'):
            base = self.url.split(':')[1]
            return base.split('/')[1].split('.')[0]

    def get_check_tldr(self):
        return self.check_tldr

    def get_priority(self):
        return self.priority

    def commit(self):
        self.repo.git.add(self.get_dirpath())
        self.repo.index.commit('Automatic execution by robots.', skip_hooks=True)

    def push(self):
        origin = self.repo.remote(name='origin')
        origin.push()

    def is_manually_repo(self):
        raise Exception


class ReferenceGithubRepos(GithubRepos):
    """A Git repository to reference when creating a helm chart for rdbox_app_market.
    """

    REPOS_DIR = os.path.join(GithubRepos.TOP_DIR, 'src')

    def __init__(self, url, branch, specific_dir_from_top='', check_tldr=False, priority=1):
        """ A Git repository to reference when creating a helm chart for rdbox_app_market.

        constructor

        Args:
            url (str): Accessible Git addresses
            branch (str): Git branch name
            specific_dir_from_top (str, optional): Specify this if the helm chart is not in the top Git directory, but is stored under that directory. Defaults to ''.
            check_tldr (bool, optional): Whether or not to verify the helm install command following "TL;DR title".. Defaults to False.
            priority (int, optional): Specifies the priority of multiple referenced Git repositories when they exist. The higher the number, the higher the priority. Defaults to 1.
        """
        if not ((url.startswith('https') or url.startswith('git')) and url.endswith('.git')):
            raise InvalidURL(url)
        self.url = url
        self.branch = branch
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.REPOS_DIR, self.get_account_name(), self.get_repository_name())
        self.check_tldr = check_tldr
        self.priority = priority
        try:
            shutil.rmtree(self.repo_dir)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.branch, depth=1)
        r_logger.debug("Branch Info")
        r_logger.debug(self.repo.head.reference.commit.hexsha)
        r_logger.debug(self.repo.head.reference.commit.message)

    def is_manually_repo(self):
        ret = False
        if self.url == 'https://github.com/rdbox-intec/helm_chart_for_rdbox.git':
            ret = True
        return ret


class RdboxGithubRepos(GithubRepos):
    """ A Git repository for managing and distributing the helm chart for rdbox_app_market.
    """

    REPOS_DIR = os.path.join(GithubRepos.TOP_DIR, 'rdbox')

    def __init__(self, url, branch, specific_dir_from_top='', check_tldr=False, priority=1):
        """ This instant is a Git repository for managing and distributing the helm chart for rdbox_app_market.

        constructor

        Args:
            url (str): Accessible Git addresses
            branch (str): Git branch name
            specific_dir_from_top (str, optional): Specify this if the helm chart is not in the top Git directory, but is stored under that directory. Defaults to ''.
            check_tldr (bool, optional): Whether or not to verify the helm install command following "TL;DR title".. Defaults to False.
            priority (int, optional): Specifies the priority of multiple referenced Git repositories when they exist. The higher the number, the higher the priority. Defaults to 1.
        """
        if not ((url.startswith('https') or url.startswith('git')) and url.endswith('.git')):
            raise InvalidURL(url)
        self.url = url
        self.branch = branch
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.REPOS_DIR, branch)
        self.check_tldr = check_tldr
        self.priority = priority
        try:
            shutil.rmtree(self.repo_dir)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        ###
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.branch, depth=1)
        ###
        try:
            for target in glob.glob(os.path.join(self.get_dirpath_with_prefix(), '*'), recursive=True):
                if os.path.isfile(target):
                    os.remove(target)
                if os.path.isdir(target):
                    shutil.rmtree(target)
        except FileNotFoundError:
            pass

    def is_manually_repo(self):
        ret = False
        if self.specific_dir_from_top == 'manually':
            ret = True
        return ret
