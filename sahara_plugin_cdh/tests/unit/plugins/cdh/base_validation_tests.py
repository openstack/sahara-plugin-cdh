# Copyright (c) 2015 Intel Corpration
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools

from sahara.plugins import exceptions as ex
from sahara.plugins import testutils as tu
from sahara_plugin_cdh.tests.unit import base

ivse = ex.InvalidVolumeSizeException
icce = ex.InvalidComponentCountException
rsme = ex.RequiredServiceMissingException
icte = ex.InvalidClusterTopology
nnce = ex.NameNodeHAConfigurationError
rmce = ex.ResourceManagerHAConfigurationError


def make_ng_dict_with_inst(counter, name, flavor, processes, count,
                           instances=None, volumes_size=None,
                           node_configs=None, **kwargs):
    if not instances:
        instances = []
        for i in range(count):
            n = next(counter)
            instance = tu.make_inst_dict("id{0}".format(n),
                                         "fake_inst{0}".format(n),
                                         management_ip='1.2.3.{0}'.format(n))
            instances.append(instance)
    return tu.make_ng_dict(name, flavor, processes, count, instances,
                           volumes_size, node_configs, **kwargs)


def get_fake_cluster_with_process(processes=None,
                                  provided_ng_list=None, **kwargs):
    processes = processes or {}
    provided_ng_list = provided_ng_list or []
    inst_counter = itertools.count(start=0)
    ng_counter = itertools.count(start=0)
    ng_id_counter = itertools.count(start=0)

    # default
    mng_ng = ('manager_ng', 1, ['CLOUDERA_MANAGER'], 1)

    mst_ng = ('master_ng', 1, ['HDFS_NAMENODE',
                               'HDFS_SECONDARYNAMENODE',
                               'YARN_RESOURCEMANAGER',
                               'YARN_JOBHISTORY',
                               ], 1)

    wkrs_ng = ('worker_ng', 1, ['HDFS_DATANODE',
                                'YARN_NODEMANAGER'], 3)

    basic_ng_list = [mng_ng, mst_ng, wkrs_ng]

    # if in default_ng_list, change it
    if 'CLOUDERA_MANAGER' in processes:
        if processes['CLOUDERA_MANAGER'] == 0:
            basic_ng_list.remove(mng_ng)
        else:
            processes['CLOUDERA_MANAGER'] -= 1

    for process in mst_ng[2]:
        if process in processes:
            if processes[process] == 0:
                mst_ng[2].remove(process)
            else:
                processes[process] -= 1

    # only consider processes set to 0
    for process in wkrs_ng[2]:
        if process in processes:
            if processes[process] == 0:
                wkrs_ng[2].remove(process)

    other_ng_list = []
    for process, count in processes.items():
        if count:
            ng = ('service_ng{0}'.format(next(ng_counter)),
                  1, [process], count)
            other_ng_list.append(ng)

    ng_list = basic_ng_list + other_ng_list + provided_ng_list

    ng_dict_list = [make_ng_dict_with_inst(
        inst_counter, *args,
        id="ng_id{0}".format(next(ng_id_counter)))
        for args in ng_list]

    return tu.create_cluster('test_cluster', 1, 'cdh',
                             '5', ng_dict_list, **kwargs)


class BaseValidationTestCase(base.SaharaTestCase):

    def _test_cluster_validation(self, exception, processes,
                                 provided_ng_list=None, kwargs_dict=None):
        provided_ng_list = provided_ng_list or []
        kwargs_dict = kwargs_dict or {}
        cluster = get_fake_cluster_with_process(processes, provided_ng_list,
                                                **kwargs_dict)
        if exception:
            self.assertRaises(exception,
                              self.module.validate_cluster_creating, cluster)
        else:
            self.module.validate_cluster_creating(cluster)

    def setUp(self):
        super(BaseValidationTestCase, self).setUp()
        self.module = None

    def _get_test_cases(self):
        """return cases with [exception expected, progresses, configs]."""
        cases = [
            [icce, {'CLOUDERA_MANAGER': 0}],
            [None, {'CLOUDERA_MANAGER': 1}],
            [icce, {'CLOUDERA_MANAGER': 2}],
            [icce, {'HDFS_NAMENODE': 0}],
            [None, {'HDFS_NAMENODE': 1}],
            [icce, {'HDFS_NAMENODE': 2}],
            [icce, {'HDFS_SECONDARYNAMENODE': 0}],
            [None, {'HDFS_SECONDARYNAMENODE': 1}],
            [icce, {'HDFS_SECONDARYNAMENODE': 2}],
            [None, {}, [],
                {'cluster_configs': {'HDFS': {'dfs_replication': 2}}}],
            [None, {}, [],
                {'cluster_configs': {'HDFS': {'dfs_replication': 3}}}],
            [icce, {}, [],
                {'cluster_configs': {'HDFS': {'dfs_replication': 4}}}],
            [ivse, {}, [(
                'worker_ng_vol', 1, ['HDFS_DATANODE', 'YARN_NODEMANAGER'],
                3, None, 20,
                {'DATANODE': {'dfs_datanode_du_reserved': 22548578304}})]],
            [None, {}, [(
                'worker_ng_vol', 1, ['HDFS_DATANODE', 'YARN_NODEMANAGER'],
                3, None, 22,
                {'DATANODE': {'dfs_datanode_du_reserved': 22548578304}})]],
            [None, {'YARN_RESOURCEMANAGER': 1}],
            [icce, {'YARN_RESOURCEMANAGER': 2}],
            [None, {'YARN_JOBHISTORY': 1}],
            [icce, {'YARN_JOBHISTORY': 2}],
            [rsme, {'YARN_JOBHISTORY': 0, 'YARN_RESOURCEMANAGER': 1}],
            [rsme, {'YARN_RESOURCEMANAGER': 0, 'YARN_NODEMANAGER': 3}],
            [None, {'YARN_RESOURCEMANAGER': 0, 'YARN_NODEMANAGER': 0}],
            [None, {'OOZIE_SERVER': 1}],
            [icce, {'OOZIE_SERVER': 2}],
            [rsme, {'YARN_NODEMANAGER': 0, 'OOZIE_SERVER': 1}],
            [rsme, {'YARN_JOBHISTORY': 0, 'OOZIE_SERVER': 1}],
            [rsme, {'HIVE_SERVER2': 0, 'HIVE_METASTORE': 1}],
            [rsme, {'HIVE_METASTORE': 0, 'HIVE_SERVER2': 1}],
            [rsme, {'HIVE_METASTORE': 0, 'HIVE_SERVER2': 0,
                    'HIVE_WEBHCAT': 1}],
            [None, {'HUE_SERVER': 1, 'OOZIE_SERVER': 1, 'HIVE_METASTORE': 1,
                    'HIVE_SERVER2': 1}],
            [icce, {'HUE_SERVER': 2, 'OOZIE_SERVER': 1, 'HIVE_METASTORE': 1,
                    'HIVE_SERVER2': 1}],
            [rsme, {'HUE_SERVER': 1, 'OOZIE_SERVER': 0}],
            [rsme, {'HUE_SERVER': 1, 'OOZIE_SERVER': 1, 'HIVE_METASTORE': 0}],
            [None, {'SPARK_YARN_HISTORY_SERVER': 0}],
            [None, {'SPARK_YARN_HISTORY_SERVER': 1}],
            [icce, {'SPARK_YARN_HISTORY_SERVER': 2}],
            [rsme, {'HBASE_MASTER': 1, 'ZOOKEEPER_SERVER': 0}],
            [icce, {'HBASE_MASTER': 1, 'ZOOKEEPER_SERVER': 1,
                    'HBASE_REGIONSERVER': 0}],
            [None, {'HBASE_MASTER': 1, 'ZOOKEEPER_SERVER': 1,
                    'HBASE_REGIONSERVER': 1}],
            [icce, {'HBASE_MASTER': 0, 'HBASE_REGIONSERVER': 1}],
            [None, {}]
        ]

        disable_anti_affinity = {'cluster_configs': {'general': {
            'Require Anti Affinity': False}}}
        cases += [
            [None, {'HDFS_JOURNALNODE': 3,
                    'ZOOKEEPER_SERVER': 1}, [], disable_anti_affinity],
            [rsme, {'HDFS_JOURNALNODE': 3,
                    'ZOOKEEPER_SERVER': 0}, [], disable_anti_affinity],
            [icce, {'HDFS_JOURNALNODE': 4,
                    'ZOOKEEPER_SERVER': 1}, [], disable_anti_affinity],
            [icce, {'HDFS_JOURNALNODE': 2,
                    'ZOOKEEPER_SERVER': 1}, [], disable_anti_affinity],
            [nnce, {'HDFS_JOURNALNODE': 3, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['HDFS_SECONDARYNAMENODE']}],
            [nnce, {'HDFS_JOURNALNODE': 3, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['HDFS_NAMENODE']}],
            [None, {'HDFS_JOURNALNODE': 3, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['HDFS_NAMENODE', 'HDFS_SECONDARYNAMENODE']}],
            [None, {'YARN_STANDBYRM': 1,
                    'ZOOKEEPER_SERVER': 1}, [], disable_anti_affinity],
            [icce, {'YARN_STANDBYRM': 2,
                    'ZOOKEEPER_SERVER': 1}, [], disable_anti_affinity],
            [rsme, {'YARN_STANDBYRM': 1,
                    'ZOOKEEPER_SERVER': 0}, [], disable_anti_affinity],
            [rmce, {'YARN_STANDBYRM': 1, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['YARN_RESOURCEMANAGER']}],
            [rmce, {'YARN_STANDBYRM': 1, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['YARN_STANDBYRM']}],
            [None, {'YARN_STANDBYRM': 1, 'ZOOKEEPER_SERVER': 1}, [],
             {'anti_affinity': ['YARN_STANDBYRM', 'YARN_RESOURCEMANAGER']}],
        ]

        cases += [
            [None, {'FLUME_AGENT': 1}],
            [icce, {'ZOOKEEPER_SERVER': 1, 'SENTRY_SERVER': 2}],
            [None, {'ZOOKEEPER_SERVER': 1, 'SENTRY_SERVER': 1}],
            [rsme, {'ZOOKEEPER_SERVER': 0, 'SENTRY_SERVER': 1}],
            [None, {'ZOOKEEPER_SERVER': 1, 'SOLR_SERVER': 1}],
            [rsme, {'ZOOKEEPER_SERVER': 0, 'SOLR_SERVER': 1}],
            [None, {'YARN_NODEMANAGER': 1, 'YARN_JOBHISTORY': 1,
                    'SQOOP_SERVER': 1}],
            [rsme, {'YARN_NODEMANAGER': 0, 'YARN_JOBHISTORY': 1,
                    'SQOOP_SERVER': 1}],
            [rsme, {'YARN_NODEMANAGER': 1, 'YARN_JOBHISTORY': 0,
                    'SQOOP_SERVER': 1}],
            # HBASE_MASTER AND HBASE_REGIONSERVER depend circularly
            [None, {'ZOOKEEPER_SERVER': 1, 'SOLR_SERVER': 1,
                    'HBASE_MASTER': 1, 'HBASE_INDEXER': 1,
                    'HBASE_REGIONSERVER': 1}],
            [rsme, {'ZOOKEEPER_SERVER': 0, 'SOLR_SERVER': 1,
                    'HBASE_MASTER': 1, 'HBASE_INDEXER': 1,
                    'HBASE_REGIONSERVER': 1}],
            [rsme, {'ZOOKEEPER_SERVER': 1, 'SOLR_SERVER': 0,
                    'HBASE_MASTER': 1, 'HBASE_INDEXER': 1,
                    'HBASE_REGIONSERVER': 1}],
            [rsme, {'ZOOKEEPER_SERVER': 1, 'SOLR_SERVER': 1,
                    'HBASE_MASTER': 0, 'HBASE_INDEXER': 1}],
        ]

        worker_with_implama = ('worker_ng', 1, ['HDFS_DATANODE',
                                                'YARN_NODEMANAGER',
                                                'IMPALAD'], 3)
        cases += [
            [None, {'IMPALA_CATALOGSERVER': 1, 'IMPALA_STATESTORE': 1,
                    'HIVE_METASTORE': 1, 'HIVE_SERVER2': 1,
                    'HDFS_DATANODE': 0, 'YARN_NODEMANAGER': 0},
             [worker_with_implama]],
            [icte, {'IMPALA_CATALOGSERVER': 1, 'IMPALA_STATESTORE': 1,
                    'HIVE_METASTORE': 1, 'HIVE_SERVER2': 1},
             []],
            [icte, {'IMPALA_CATALOGSERVER': 1, 'IMPALA_STATESTORE': 1,
                    'HIVE_METASTORE': 1, 'HIVE_SERVER2': 1},
             [worker_with_implama]],
            [rsme, {'IMPALA_CATALOGSERVER': 1, 'IMPALA_STATESTORE': 0,
                    'HIVE_METASTORE': 1, 'HIVE_SERVER2': 1,
                    'HDFS_DATANODE': 0, 'YARN_NODEMANAGER': 0},
             [worker_with_implama]],
            [rsme, {'IMPALA_CATALOGSERVER': 1, 'IMPALA_STATESTORE': 1,
                    'HIVE_METASTORE': 0, 'HIVE_SERVER2': 1,
                    'HDFS_DATANODE': 0, 'YARN_NODEMANAGER': 0},
             [worker_with_implama]]

        ]

        cases += [
            [None, {'KMS': 1}],
            [icce, {'KMS': 2}]
        ]

        return cases

    def test_validate_cluster_creating(self):
        cases = self._get_test_cases()

        for case in cases:
            self._test_cluster_validation(*case)

    def test_validate_additional_ng_scaling(self):
        # valid scaling
        cluster = get_fake_cluster_with_process({})
        additional = {cluster.node_groups[2].id: 4}
        self.module.validate_additional_ng_scaling(cluster, additional)

        # node processes unscalable
        cluster = get_fake_cluster_with_process({})
        additional = {cluster.node_groups[0].id: 2}
        self.assertRaises(ex.NodeGroupCannotBeScaled,
                          self.module.validate_additional_ng_scaling, cluster,
                          additional)

        # scaling without resourcemanager
        cluster = get_fake_cluster_with_process({"YARN_RESOURCEMANAGER": 0})
        additional = {cluster.node_groups[2].id: 4}
        self.assertRaises(ex.NodeGroupCannotBeScaled,
                          self.module.validate_additional_ng_scaling, cluster,
                          additional)

    def test_validate_existing_ng_scaling(self):
        # valid scaling, add datanodes
        cluster = get_fake_cluster_with_process({})
        existing = {cluster.node_groups[2].id: 4}
        self.module.validate_existing_ng_scaling(cluster, existing)

        # node processes unscalable
        cluster = get_fake_cluster_with_process({})
        existing = {cluster.node_groups[0].id: 2}
        self.assertRaises(ex.NodeGroupCannotBeScaled,
                          self.module.validate_existing_ng_scaling, cluster,
                          existing)

        # datanode count less than replicas
        cfg = {'HDFS': {'dfs_replication': 3}}
        cluster = get_fake_cluster_with_process({},
                                                cluster_configs=cfg)
        existing = {cluster.node_groups[2].id: 2}
        self.assertRaises(ex.ClusterCannotBeScaled,
                          self.module.validate_existing_ng_scaling, cluster,
                          existing)

        # datanode count more than replicas
        cfg = {'HDFS': {'dfs_replication': 2}}
        cluster = get_fake_cluster_with_process({},
                                                cluster_configs=cfg)
        existing = {cluster.node_groups[2].id: 2}
        self.module.validate_existing_ng_scaling(cluster, existing)
