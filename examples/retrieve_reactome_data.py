from lifelike_gds.graph_sources.neo4j_utils import Neo4jConnection
from lifelike_gds.graph_sources.reactome_db import ReactomeDB
import os, dotenv

from lifelike_gds.network import graph_source

dotenv.load_dotenv()

query = """
match (r:ReferenceMolecule)-[:referenceEntity]-(p:PhysicalEntity)
    where r.databaseName = 'ChEBI' and r.identifier in $chebi_ids
    return r.stId as chebi, r.name, p.stId, p.compartment, p.synonyms
    order by p.compartment
"""

def run_query_with_connection():
    connect = Neo4jConnection(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE")
    )
    df = connect.get_dataframe(query, parameters={"chebi_ids": ["17336"]})
    print(df)

def run_query_with_database():
    db = ReactomeDB()
    df = db.get_dataframe(query, parameters={"chebi_ids": ["17336"]})
    print(df)


if __name__ == "__main__":
    # run_query_with_connection()
    run_query_with_database()