#!/usr/bin/env python3
import textwrap
import pytest

from rdbox_app_market.values_yaml import ValuesYaml, FilterOfStorageClass


class TestValuesYaml(object):
    def __dummy_readlines(self, test_text):
        _readlines_result = [_txt + '\n' for _txt in test_text.split('\n')]
        _readlines_result[-1] = ''
        return _readlines_result

    def test_constructor(self):
        values_yaml = ValuesYaml('/tmp', 'test')
        assert values_yaml.module_name == 'test'
        assert values_yaml.full_path == '/tmp/values.yaml'

    def test_has_active_nodeSelector(self, mocker):
        # test True
        test_text = textwrap.dedent("""\
            affinity: {}
            nodeSelector: {}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        values_yaml = ValuesYaml('/tmp', 'test')
        assert values_yaml.has_active_nodeSelector() is True
        # test False
        test_text = textwrap.dedent("""\
            affinity: {}
            # nodeSelector: {}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        assert values_yaml.has_active_nodeSelector() is False
        # test False
        mocker.patch.object(ValuesYaml, 'readlines').side_effect = FileNotFoundError()
        assert values_yaml.has_active_nodeSelector() is False

    def test_has_commentout_nodeSelector(self, mocker):
        # test True
        test_text = textwrap.dedent("""\
            affinity: {}
            # nodeSelector: {}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        values_yaml = ValuesYaml('/tmp', 'test')
        assert values_yaml.has_commentout_nodeSelector() is True
        # test False
        test_text = textwrap.dedent("""\
            affinity: {}
            #   nodeSelector: {}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        assert values_yaml.has_commentout_nodeSelector() is False
        # test False
        mocker.patch.object(ValuesYaml, 'readlines').side_effect = FileNotFoundError()
        assert values_yaml.has_commentout_nodeSelector() is False

    def test_correct_commentout_nodeSelector(self, mocker):
        # test True
        test_text = textwrap.dedent("""\
            affinity: {}
            # nodeSelector: {}
            tolerations: []
            """)
        expect_text = textwrap.dedent("""\
            affinity: {}
            nodeSelector: {} #{}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.correct_commentout_nodeSelector()
        assert is_changed is True
        assert file_text == expect_text
        # test False
        test_text = textwrap.dedent("""\
            affinity: {}
            #   nodeSelector: {}
            tolerations: []
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        file_text, is_changed = values_yaml.correct_commentout_nodeSelector()
        assert is_changed is False
        assert file_text == test_text
        # test Exception
        mocker.patch.object(ValuesYaml, 'readlines').side_effect = FileNotFoundError()
        with pytest.raises(FileNotFoundError):
            values_yaml.correct_commentout_nodeSelector()

    def test_has_expected_structure_for_imagetag(self, mocker):
        # test True
        test_text = textwrap.dedent("""\
            replicaCount: 1
            image:
              repository: registry
              tag: 2.7.1
              pullPolicy: IfNotPresent
            nodeSelector: {}
            affinity: {}
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        values_yaml = ValuesYaml('/tmp', 'test')
        assert values_yaml.has_expected_structure_for_imagetag() is True
        # test False
        test_text = textwrap.dedent("""\
            replicaCount: 1
            image:
              repository: registry
              pullPolicy: IfNotPresent
            nodeSelector: {}
            affinity: {}
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        assert values_yaml.has_expected_structure_for_imagetag() is False
        # test False
        mocker.patch.object(ValuesYaml, 'readlines').side_effect = FileNotFoundError()
        assert values_yaml.has_expected_structure_for_imagetag() is False

    def test_specify_storageClass_for_rdbox_global(self, mocker):
        # test data
        test_text = textwrap.dedent("""\
            ##
            # global:
            #   imageRegistry: myRegistryName
            #   imagePullSecrets:
            #     - myRegistryKeySecretName
            #   storageClass: myStorageClass
            """)
        expect_text = textwrap.dedent("""\
            ##
            global:
            #   imageRegistry: myRegistryName
            #   imagePullSecrets:
            #     - myRegistryKeySecretName
              storageClass: openebs-jiva-rdbox
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        mocker.patch.object(FilterOfStorageClass, '_FilterOfStorageClass__get_indent_info').return_value = [], 2
        mocker.patch('rdbox_app_market.config.get').return_value = 'openebs-jiva-rdbox'
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.specify_storageClass_for_rdbox()
        assert is_changed is True
        assert file_text == expect_text

    def test_specify_storageClass_for_rdbox_no_storageClass(self, mocker):
        # test data
        test_text = textwrap.dedent("""\
            ##
            image:
              registry: docker.io
              ## Comment
              repository: rdbox/rdbox
              tag: v0.2.0
              pullPolicy: IfNotPresent
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.specify_storageClass_for_rdbox()
        assert is_changed is False
        assert file_text == test_text

    def test_specify_storageClass_for_rdbox_no_storageClass_in_global(self, mocker):
        # test data
        test_text = textwrap.dedent("""\
            ##
            # global:
            #   imageRegistry: myRegistryName
            #   imagePullSecrets:
            #     - myRegistryKeySecretName
            ##
            persistence:
              enable: true
              # storageClass: "-"
            """)
        expect_text = textwrap.dedent("""\
            ##
            # global:
            #   imageRegistry: myRegistryName
            #   imagePullSecrets:
            #     - myRegistryKeySecretName
            ##
            persistence:
              enable: true
              storageClass: openebs-jiva-rdbox
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        mocker.patch.object(FilterOfStorageClass, '_FilterOfStorageClass__get_indent_info').return_value = \
            [-1, -1, -1, -1, -1, -1, 0, 2, -1, 0], 2
        mocker.patch('rdbox_app_market.config.get').return_value = 'openebs-jiva-rdbox'
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.specify_storageClass_for_rdbox()
        assert is_changed is True
        assert file_text == expect_text

    def test_specify_storageClass_for_rdbox_separate(self, mocker):
        # test data
        test_text = textwrap.dedent("""\
            persistence:
              enable: true
              # storageClass: "-"
            """)
        expect_text = textwrap.dedent("""\
            persistence:
              enable: true
              storageClass: openebs-jiva-rdbox
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        mocker.patch.object(FilterOfStorageClass, '_FilterOfStorageClass__get_indent_info').return_value = \
            [0, 2, -1, 0], 2
        mocker.patch('rdbox_app_market.config.get').return_value = 'openebs-jiva-rdbox'
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.specify_storageClass_for_rdbox()
        assert is_changed is True
        assert file_text == expect_text

    def test_specify_storageClass_for_rdbox_separate_anomalous_comment(self, mocker):
        # test data
        test_text = textwrap.dedent("""\
            persistence:
              enable: true
            #  storageClass: "-"
              size: 8Gi
            """)
        expect_text = textwrap.dedent("""\
            persistence:
              enable: true
              storageClass: openebs-jiva-rdbox
              size: 8Gi
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        mocker.patch.object(FilterOfStorageClass, '_FilterOfStorageClass__get_indent_info').return_value = \
            [0, 2, -1, 2, 0], 2
        mocker.patch('rdbox_app_market.config.get').return_value = 'openebs-jiva-rdbox'
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed = values_yaml.specify_storageClass_for_rdbox()
        assert is_changed is True
        assert file_text == expect_text

    def test_specify_nodeSelector_for_rdbox(self, mocker):
        test_text = textwrap.dedent("""\
            replicaCount: 1
            image:
              repository: registry
              tag: 2.7.1
              pullPolicy: IfNotPresent
            nodeSelector: {}
            affinity: {}
            """)
        expect_text = textwrap.dedent("""\
            replicaCount: 1
            image:
              repository: registry
              tag: 2.7.1
              pullPolicy: IfNotPresent
            nodeSelector:
              beta.kubernetes.io/os: linux
            affinity: {}
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        # assert
        values_yaml = ValuesYaml('/tmp', 'test')
        file_text, is_changed, multi_arch_dict = values_yaml.specify_nodeSelector_for_rdbox()
        assert is_changed is True
        assert file_text == expect_text
        assert multi_arch_dict == {'_': 'registry'}

    def test_specify_ingress_for_rdbox_str_hosts(self, mocker):
        test_text = textwrap.dedent("""\
            replicaCount: 1
            ingress:
              enabled: false
              path: /
              hosts:
                - chart-example.local
              annotations: {}
                # kubernetes.io/ingress.class: nginx
                # kubernetes.io/tls-acme: "true"
              labels: {}
              tls:
                # Secrets must be manually created in the namespace.
                # - secretName: chart-example-tls
                #   hosts:
                #     - chart-example.local
            affinity: {}
            """)
        expect_text = textwrap.dedent("""\
            replicaCount: 1
            ingress:
              enabled: true
              path: /
              hosts:
            #    - chart-example.local
                - docker-registry.rdbox.lan
              annotations:
                kubernetes.io/ingress.class: nginx
                kubernetes.io/tls-acme: "true"
              labels: {}
              tls:
                - hosts:
                  - '*.rdbox.lan'
                  secretName: rdbox.lan
                # Secrets must be manually created in the namespace.
                # - secretName: chart-example-tls
                #   hosts:
                #     - chart-example.local
            affinity: {}
            """)
        mocker.patch.object(ValuesYaml, 'readlines').return_value = self.__dummy_readlines(test_text)
        mocker.patch.object(ValuesYaml, 'write_text').return_value = None
        mocker.patch('rdbox_app_market.config.get').return_value = 'rdbox.lan'
        # assert
        values_yaml = ValuesYaml('/tmp', 'docker-registry')
        file_text, is_changed = values_yaml.specify_ingress_for_rdbox()
        print(file_text)
        assert is_changed is True
        assert file_text == expect_text
