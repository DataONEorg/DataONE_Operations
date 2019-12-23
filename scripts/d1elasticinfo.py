"""
Basic infomration about an elasticsearch server
"""

import sys
import logging
import argparse
import d1_admin_tools
from sshtunnel import SSHTunnelForwarder
from gypp import passwords_yaml
from elasticsearch import Elasticsearch

def getOldestNewestDates(ES, index_name, field_name="@timestamp"):
    query = {
        "_source": [field_name],
        "sort":[
            {
                field_name: {
                    "order":"desc"
                }
            }
        ],
        "size": 1
    }
    result = ES.search(index_name, query)
    res = {"tmax":result['hits']['hits'][0]['_source'][field_name]}
    query["sort"][0][field_name]["order"] = "asc"
    result = ES.search(index_name, query)
    res["tmin"] = result['hits']['hits'][0]['_source'][field_name]
    return res


def getNumberOfRecords(ES, index_name, query="*:*"):
    result = ES.count(index=index_name, expand_wildcards="all")
    return result["count"]


def getIndices(ES, match="*"):
    indices = ES.indices.get_alias(match)
    return sorted(indices.keys())

def getDistinctValues(ES, index, fields=[]):
    if len(fields) < 1:
        return {}
    query = {
        "size":0,
        "aggs":{

        }
    }
    counter = 0
    for field in fields:
        query["aggs"][f"uniq_{counter}"] = {"terms":{"field":field}}
        counter = counter + 1
    result = ES.search(index, query)
    counter = 0
    res = {}
    for field in fields:
        res[field] = result['aggregations'][f"uniq_{counter}"]['buckets']
    return res


def getElasticInfo(index_match="*", ts_field="@timestamp", fields=[]):
    ES = Elasticsearch()
    indices = getIndices(ES, index_match)
    for index in indices:
        tminmax = {"tmin":"N/A", "tmax":"N/A"}
        if ts_field is not '':
            tminmax = getOldestNewestDates(ES, index)
        numrecs = getNumberOfRecords(ES, index)
        print(f"{index:>34} {numrecs:>10} {tminmax['tmin']:>26} {tminmax['tmax']:>26}")
    if len(fields) > 0:
        for index in indices:
            print(f"\nFor index = {index}")
            res = getDistinctValues(ES, index, fields)
            for field in fields:
                print(f"{field}  has {len(res[field])} distinct values:")
                for aval in res[field]:
                    print(f"    {aval['key']} : {aval['doc_count']}")



def main():
    """
    -i --index:       Name pattern for indices to examine
    -l --log_level:   flag to turn on logging, more means more detailed logging.

    :return: int for sys.exit()
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-i', '--index',
                        default='*',
                        help='Name of index to examine')
    parser.add_argument('-t', '--timestamp',
                        default='@timestamp',
                        help='Name of timestamp field')
    parser.add_argument("-F", "--field",
                        default=[],
                        action="append",
                        nargs="*",
                        help="List distinct values for specified field")
    args, config = d1_admin_tools.defaultScriptMain(parser)
    logger = logging.getLogger("main")

    getElasticInfo(args.index, ts_field=args.timestamp, fields=args.field[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
