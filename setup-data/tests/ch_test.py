from .context import src
import unittest
import json

class TestSuite(unittest.TestCase):

    def test_smoke_ch(self):
        table = src.ch.CHTable(
            name='my-table',
            id_column=src.ch.CHColumn(name='id', type='Int64', codec=None),
            ts_column=src.ch.CHColumn(name='dt', type='DateTime64(6)', codec="ZSTD"),
            columns=[
                src.ch.CHColumn(name='column1', type='Int64', codec="Delta, ZSTD"),
                src.ch.CHColumn(name='column2', type='Float64', codec="Delta, ZSTD")
            ],
            kafka_topic='my-topic',
        )

        for query in table.distributed_queries():
            print("-------------------------")
            print(query)

        for query in table.kafka_queries(kafka_bootstrap_host='bootstrap.kafka.local:9092'):
            print("-------------------------")
            print(query)

        table_last = src.ch.CHAnalyticalTable(
            table=table,
            aggregator=src.ch.CHAggregatorLast(),
        )

        for query in table_last.all_create_queries():
            print("-------------------------")
            print(query)

        table_interval = src.ch.CHAnalyticalTable(
            table=table,
            aggregator=src.ch.CHAggregatorInterval(
                group_functions=['toDate','toStartOfDay'],
                name="day",
                aggregations=[
                    src.ch.CHAggregation(type="avg"),
                    src.ch.CHAggregation(type="quantiles", args_agg=["0.1", "0.9"])
                ]
            )
        )
        
        for query in table_interval.all_create_queries():
            print("-------------------------")
            print(query)
        
        assert True

    def test_ch_from_json(self):
        json_data = """
{
	"tables":[
		{
			"name":"my-table",
			"id_column":{
				"name":"id",
				"type":"Int64"
			},
			"ts_column":{
				"name":"id",
				"type":"Datetime64(6)",
				"codec":[
					"ZSTD"
				]
			},
			"columns":[
				{
					"name":"column1",
					"type":"Int64",
					"codec":[
						"Delta",
						"ZSTD"
					]
				},
				{
					"name":"column2",
					"type":"Float64",
					"codec":[
						"Delta",
						"ZSTD"
					]
				}
			],
			"kafka_topic":"my-topic",
			"kafka_bootstrap_host":"bootstrap.kafka.local:9092"
		}
	],
	"analytical_tables":[
		{
			"table":"my-table",
			"aggregator":{
				"type":"last"
			}
		},
		{
			"table":"my-table",
			"aggregator":{
				"type":"interval",
				"name":"day",
				"group_functions":[
					"toDate",
					"toStartOfDay"
				],
				"aggregations":[
					{
						"type":"avg"
					},
					{
						"type":"quantiles",
						"args_agg":[
							"0.1",
							"0.9"
						]
					}
				]
			}
		}
	]
}
"""

        tables = src.ch.load_from_dict(json.loads(json_data))

        for table in tables:
            for query in table.all_create_queries():
                print("-------------------------")
                print(query) 

if __name__ == '__main__':
    unittest.main()
