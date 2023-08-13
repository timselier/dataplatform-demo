from typing import Callable
from .util import *
import os

SEPERATOR = ",\n"

class CHColumn:
    def __init__(self, name, type, codec=None):
        self.name = name
        self.type = type
        self.codec = codec

    @staticmethod
    def from_dict(dict_):
        return CHColumn(**dict_)
    
    def to_ddl(self, with_codec=True) -> str:
        return " ".join(x for x in (
            f"`{self.name}`", 
            self.type, 
            f"CODEC({','.join(self.codec)})" if with_codec and self.codec is not None else None
            ) if x is not None )

class CHTable:
    def __init__(self, 
                 name: str, 
                 id_column: CHColumn, 
                 ts_column: CHColumn, 
                 columns: list[CHColumn],
                 kafka_topic: str,
                 kafka_bootstrap_host: str
                   ):
        self.name = name
        self.id_column = id_column
        self.ts_column = ts_column
        self.columns = columns
        self.kafka_topic = kafka_topic
        self.kafka_bootstrap_host = kafka_bootstrap_host

        
    @staticmethod
    def from_dict(dict_):
        dict_["id_column"] = CHColumn.from_dict(dict_["id_column"])
        dict_["ts_column"] = CHColumn.from_dict(dict_["ts_column"])
        dict_["columns"] = [CHColumn.from_dict(c) for c in dict_["columns"]]
        return CHTable(**dict_)
    
    def all_create_queries(self):
        for query in self.distributed_queries():
            yield query
        
        for query in self.kafka_queries(kafka_bootstrap_host=self.kafka_bootstrap_host):
            yield query   

    def distributed_queries(self):
        yield f"""
CREATE TABLE IF NOT EXISTS `{self.name}_shard` ON CLUSTER `cluster`
({ SEPERATOR.join(c.to_ddl() for c in [self.id_column, self.ts_column, *self.columns]) }) 
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{{shard}}/{self.name}_shard', '{{replica}}' )
ORDER BY ({self.id_column.name}, `{self.ts_column.name}`)
PARTITION BY toYYYYMM(`{self.ts_column.name}`)
"""

        yield f"""
CREATE TABLE IF NOT EXISTS `{self.name}` ON CLUSTER `cluster` AS {self.name}_shard
ENGINE = Distributed(cluster, default, {self.name}_shard, {self.id_column.name})
"""

    def kafka_queries(self, kafka_bootstrap_host):
        if self.kafka_topic is None:
            return []
        
        yield  f"""
CREATE TABLE IF NOT EXISTS default.{self.name}_kafka ON CLUSTER `cluster`
({ SEPERATOR.join(c.to_ddl(with_codec=False) for c in [self.id_column, self.ts_column, *self.columns]) }) 
ENGINE = Kafka('{kafka_bootstrap_host}', '{self.kafka_topic}', 'clickhouse', 'JSONEachRow') 
SETTINGS kafka_thread_per_consumer = 0, kafka_num_consumers = 1, kafka_skip_broken_messages=99999;
"""

        yield f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS default.{self.name}_kafka_mv ON CLUSTER `cluster` 
TO {self.name}_shard AS
SELECT * FROM default.{self.name}_kafka;
"""


class CHAggregation():
    def __init__(self, type : str, args_agg : list[str] = None, args_func : list[str] = None):
        self.type=type
        self.args_agg=args_agg
        self.args_func=args_func

    @staticmethod
    def from_dict(dict_):
        return CHAggregation(**dict_)

    def slug(self):
        return slugify("_".join([
            self.type, 
            *(self.args_agg if self.args_agg is not None else []),
            *(self.args_func if self.args_func is not None else [])
            ]))

class CHAggregator():
    def __init__(self):
        pass

    @staticmethod
    def from_dict(dict_):
        type_ = dict_["type"]
        del dict_["type"]

        if type_ == "last":
            return CHAggregatorLast.from_dict(dict_)
        
        elif type_ == "interval":
            return CHAggregatorInterval.from_dict(dict_)
        else:
            return None
    
class CHAggregatorLast(CHAggregator):
    def __init__(self):
        self.name = "last"

    @staticmethod
    def from_dict(dict_):
        return CHAggregatorLast(**dict_)
    
    def to_ddl_shard(self, table):
        yield f"`{table.id_column.name}`"
        yield f"maxState(`{table.ts_column.name}`) as `{table.ts_column.name}_state`"

        for column in table.columns:
            yield f"argMaxState(`{column.name}`, `{table.ts_column.name}`) as `{column.name}_state`"

    def to_ddl_view(self, table):
        yield f"`{table.id_column.name}`"
        yield f"maxMerge(`{table.ts_column.name}_state`) as `{table.ts_column.name}`"

        for column in table.columns:
            yield f"argMaxMerge(`{column.name}_state`) as `{column.name}`"

    def group_by(self, table : CHTable):
        yield f"`{table.id_column.name}`"
        

class CHAggregatorInterval(CHAggregator):
    def __init__(self, group_functions: list[str], name: str, aggregations = list[CHAggregation]):
        self.group_functions=group_functions
        self.name=name
        self.aggregations=aggregations

    @staticmethod
    def from_dict(dict_):
        dict_["aggregations"] = [CHAggregation.from_dict(a) for a in dict_["aggregations"]]

        return CHAggregatorInterval(**dict_)
    
    def to_ddl_shard(self, table : CHTable ):
        yield f"`{table.id_column.name}`"

        group_select = f"`{table.ts_column.name}`"
        for group_function in self.group_functions[::-1]:
            group_select = f"{group_function}({group_select})"

        yield f"{group_select} AS `{self.name}`"

        for column in table.columns:
            for aggregation in self.aggregations:
                args_agg_str = f"({ ', '.join(aggregation.args_agg) })" if aggregation.args_agg is not None else ""
                columns_str = ", ".join(f"`{col}`" for col in [column.name, *(aggregation.args_func if aggregation.args_func is not None else [])])
                yield f"""{aggregation.type}State{args_agg_str}({columns_str}) AS `{column.name}_{aggregation.slug()}_state`"""

    def to_ddl_view(self, table : CHTable ):
        yield f"`{table.id_column.name}`"
        yield f"`{self.name}`"

        for column in table.columns:
            for aggregation in self.aggregations:
                args_str = f"({ ','.join(aggregation.args_agg) })" if aggregation.args_agg is not None else ""
                yield f"""{aggregation.type}Merge{args_str}(`{column.name}_{aggregation.slug()}_state`) AS `{column.name}_{aggregation.slug()}`"""

    def group_by(self, table : CHTable):
        yield f"`{table.id_column.name}`"
        yield f"`{self.name}`"

class CHAnalyticalTable:
    def __init__(self, table : CHTable, aggregator : CHAggregator ):
        self.table=table
        self.aggregator=aggregator
 
    @staticmethod
    def from_dict(dict_):
        assert type(dict_["table"]) == CHTable
        dict_["aggregator"] = CHAggregator.from_dict(dict_["aggregator"])
        return CHAnalyticalTable(**dict_)


    def all_create_queries(self):

        yield f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS `{self.table.name}_{self.aggregator.name}_shard` on CLUSTER `cluster`
ENGINE = ReplicatedAggregatingMergeTree('/clickhouse/tables/{{shard}}/{self.table.name}_{self.aggregator.name}_shard', '{{replica}}' )
ORDER BY `{self.table.id_column.name}`
AS SELECT { SEPERATOR.join(self.aggregator.to_ddl_shard(self.table)) }
FROM `{self.table.name}_shard`
GROUP BY { ", ".join(self.aggregator.group_by(self.table)) }
"""

        yield f"""
CREATE TABLE IF NOT EXISTS `{self.table.name}_{self.aggregator.name}_dist` ON CLUSTER `cluster`
AS `{self.table.name}_{self.aggregator.name}_shard`
ENGINE = Distributed(cluster, default, {self.table.name}_{self.aggregator.name}_shard, {self.table.id_column.name})
"""

        yield f"""
CREATE OR REPLACE VIEW weatherStationObservation_{self.aggregator.name} ON CLUSTER `cluster`
AS SELECT { SEPERATOR.join(self.aggregator.to_ddl_view(self.table)) }
FROM `{self.table.name}_{self.aggregator.name}_dist`
GROUP BY { ", ".join(self.aggregator.group_by(self.table)) }
"""


def load_from_dict(dict_, kafka_bootstrap_host):
    tables = {table.name: table for table in [CHTable.from_dict(dict(kafka_bootstrap_host=kafka_bootstrap_host, **x)) for x in dict_["tables"]]}
    analytical_tables = [CHAnalyticalTable.from_dict(dict(table=tables[x['table']], aggregator=x["aggregator"])) for x in dict_["analytical_tables"]]
    return (list(tables.values()), list(analytical_tables))
