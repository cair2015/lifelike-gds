from neo4j import GraphDatabase

class Neo4jGraphSource:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
        
    
    def get_physical_entity_by_reference(self, refrenence_db: str, reference_ids: list[str]) -> dict:
        """
        Get a physical entity by its reference database and reference ID.
        Args:
            refrenence_db (str): The reference database (e.g., "UniProt", "ChEBI").
            reference_ids (list[str]): The reference IDs (e.g., ["P12345"] for UniProt, ["12345"] for ChEBI).
        """
        query = f"""
        MATCH (pe:PhysicalEntity)-[:referenceEntity]->(ref:ReferenceEntity)
        WHERE ref.databaseName = '{refrenence_db}' AND ref.identifier in {reference_ids}
        return pe.stId, pe.name, pe.displayName, pe.compartment, ref.stId as referenceId
        """
        results = self.run_query(query)
        return results
    

if __name__ == "__main__":
    import os, dotenv
    dotenv.load_dotenv()
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    graph_source = Neo4jGraphSource(neo4j_uri, neo4j_username, neo4j_password)
    results = graph_source.get_physical_entity_by_reference("ChEBI", ["37565", "456215"])
    print(results)