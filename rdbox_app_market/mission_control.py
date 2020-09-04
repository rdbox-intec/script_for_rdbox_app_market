#!/usr/bin/env python3
import os
import shutil

from logging import getLogger

from rdbox_app_market.github import GithubRepos, RdboxGithubRepos, ReferenceGithubRepos
from rdbox_app_market.app_market import Collector, Publisher

r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


class MissionControl(object):
    @classmethod
    def launch(cls, exec_publish: bool):
        raise Exception


class VendorMissionControl(MissionControl):
    @classmethod
    def launch(cls, exec_publish: bool):
        #########################
        top_dir_path = GithubRepos.TOP_DIR
        try:
            shutil.rmtree(top_dir_path)
        except FileNotFoundError:
            os.makedirs(top_dir_path, exist_ok=True)
        #########################
        try:
            # ----------------- #
            src_repos = []
            src_repos.append(ReferenceGithubRepos(
                'https://github.com/bitnami/charts.git',
                'master',
                specific_dir_from_top='bitnami',
                check_tldr=True,
                priority=999))
            src_repos.append(ReferenceGithubRepos(
                'https://github.com/helm/charts.git',
                'master',
                specific_dir_from_top='stable',
                check_tldr=False,
                priority=500))
            src_repos.append(ReferenceGithubRepos(
                'https://github.com/helm/charts.git',
                'master',
                specific_dir_from_top='incubator',
                check_tldr=False,
                priority=499))
            #####################
            dst_repo_master = RdboxGithubRepos(
                'git@github.com:rdbox-intec/rdbox_app_market.git',
                'master',
                specific_dir_from_top='bot-gen',
                check_tldr=False,
                priority=999)
            # ----------------- #
            collector = Collector(src_repos, dst_repo_master)
            isolations_collect_result, dependons_collect_result = collector.work()
            # ----------------- #
            dst_repo_ghpage = RdboxGithubRepos(
                'git@github.com:rdbox-intec/rdbox_app_market.git',
                'gh-pages',
                specific_dir_from_top='bot-gen',
                check_tldr=False,
                priority=999)
            # ----------------- #
            publisher = Publisher(isolations_collect_result, dependons_collect_result, dst_repo_ghpage)
            _ = publisher.work(exec_publish)
            return True
        except Exception:
            import traceback
            r_logger.error(traceback.format_exc())
            return False


class RDBOXMissionControl(MissionControl):
    @classmethod
    def launch(cls, exec_publish: bool):
        #########################
        top_dir_path = GithubRepos.TOP_DIR
        try:
            shutil.rmtree(top_dir_path)
        except FileNotFoundError:
            os.makedirs(top_dir_path, exist_ok=True)
        #########################
        try:
            # ----------------- #
            src_repos = []
            src_repos.append(ReferenceGithubRepos(
                'https://github.com/rdbox-intec/helm_chart_for_rdbox.git',
                'master',
                specific_dir_from_top='rdbox',
                check_tldr=False,
                priority=999))
            #####################
            dst_repo_master = RdboxGithubRepos(
                'git@github.com:rdbox-intec/rdbox_app_market.git',
                'master',
                specific_dir_from_top='manually',
                check_tldr=False,
                priority=999)
            # ----------------- #
            collector = Collector(src_repos, dst_repo_master)
            isolations_collect_result, dependons_collect_result = collector.work()
            # ----------------- #
            dst_repo_ghpage = RdboxGithubRepos(
                'git@github.com:rdbox-intec/rdbox_app_market.git',
                'gh-pages',
                specific_dir_from_top='manually',
                check_tldr=False,
                priority=999)
            # ----------------- #
            publisher = Publisher(isolations_collect_result, dependons_collect_result, dst_repo_ghpage)
            _ = publisher.work(exec_publish)
            return True
        except Exception:
            import traceback
            r_logger.error(traceback.format_exc())
            return False
