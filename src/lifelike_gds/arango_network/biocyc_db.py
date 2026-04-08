"""ArangoDB-specific BioCyc database adapter."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from lifelike_gds.arango_network.database import Database
from lifelike_gds.network.biocyc import (
    Biocyc,
    CURRENCY_LABEL,
    CURRENCY_METABOLITES,
    EDGE_DESC_DICT,
)
from lifelike_gds.utils import get_id


class BiocycDB(Database):
    """ArangoDB query adapter for the BioCyc graph."""

    def __init__(
        self,
        dbname: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__("biocyc", dbname=dbname, uri=uri, username=username, password=password)

    def get_nodes_by_attr(
        self,
        attr_values: List[str],
        attr_name: str,
        node_label: str = "db_BioCyc",
    ):
        return super().get_nodes_by_attr(attr_values, attr_name, node_label)

    def get_graph_data_for_networkx(
        self,
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
        exclude_nodes: Optional[List[int]] = None,
    ):
        exclude_ids = [get_id(node) for node in exclude_nodes] if exclude_nodes else []
        filters_n = []
        filters_m = []
        filters_r = []
        if exclude_currency:
            filters_n.append(f'"{CURRENCY_LABEL}" NOT IN n.labels')
            filters_m.append(f'"{CURRENCY_LABEL}" NOT IN m.labels')
        if exclude_secondary:
            filters_r.append("r.SECONDARY == null")
        if exclude_ids:
            filters_n.append("TO_NUMBER(n._key) NOT IN @exclude_ids")
            filters_m.append("TO_NUMBER(m._key) NOT IN @exclude_ids")

        node_filter = f"FILTER {' AND '.join(filters_n)}" if filters_n else ""
        rel_filters = "\n".join(
            filter(
                None,
                [
                    f"FILTER {' AND '.join(filters_n)}" if filters_n else "",
                    f"FILTER {' AND '.join(filters_m)}" if filters_m else "",
                    f"FILTER {' AND '.join(filters_r)}" if filters_r else "",
                ],
            )
        )

        node_query = f"""
            FOR n IN biocyc
                {node_filter}
                RETURN {{ node_id: TO_NUMBER(n._key) }}
        """
        rel_query = f"""
            FOR n IN biocyc
                {f"FILTER {' AND '.join(filters_n)}" if filters_n else ''}
                FOR m, r IN OUTBOUND n GRAPH "all"
                    {f"FILTER {' AND '.join(filters_m)}" if filters_m else ''}
                    {f"FILTER {' AND '.join(filters_r)}" if filters_r else ''}
                    RETURN {{
                        source: TO_NUMBER(n._key),
                        target: TO_NUMBER(m._key),
                        type: r.label
                    }}
        """
        parameters = {"exclude_ids": exclude_ids} if exclude_ids else {}
        return self.get_dataframe(node_query, **parameters), self.get_dataframe(rel_query, **parameters)

    def get_node_data_for_excel(self, node_ids: List[int]):
        query = """
            FOR n IN biocyc
                FILTER TO_NUMBER(n._key) IN @nids
                    LET lbls = (FOR l IN n.labels FILTER !STARTS_WITH(l, 'db_') RETURN l)
                    RETURN {
                        id: TO_NUMBER(n._key),
                        eid: n.eid,
                        displayName: n.displayName,
                        description: n.detail,
                        entityType: n.entityType,
                        labels: lbls
                    }
        """
        df = self.get_dataframe(query, nids=node_ids)

        query = """
            LET nodes = (
                FOR n IN biocyc
                    FILTER TO_NUMBER(n._key) IN @nids
                    RETURN n
            )
            FOR r IN UNION(
                (
                    FOR n IN nodes
                        FILTER 'Reaction' IN n.labels
                        FOR a IN INBOUND n catalyzes
                            FOR b IN 0..5 INBOUND a component_of
                                FOR g IN INBOUND b encodes
                                    FILTER "Gene" IN g.labels
                                    COLLECT id = TO_NUMBER(n._key) INTO enrichment = g.name
                        RETURN {id: id, enrichment: enrichment}
                ),
                (
                    FOR n IN nodes
                        FILTER 'Protein' IN n.labels
                        FOR b IN 0..5 INBOUND n component_of
                            FOR g IN INBOUND b encodes
                                FILTER "Gene" IN g.labels
                                COLLECT id = TO_NUMBER(n._key) INTO enrichment = g.name
                        RETURN {id: id, enrichment: enrichment}
                ),
                (
                    FOR n IN nodes
                        FILTER 'Compound' IN n.labels
                        FOR r IN ANY n GRAPH "all"
                            FILTER "Reaction" IN r.labels
                            FOR p IN ANY r GRAPH "all"
                                FILTER "Pathway" IN p.labels
                                COLLECT id = TO_NUMBER(n._key) INTO enrichment = p.name
                        RETURN {id: id, enrichment: enrichment}
                )
            )
                RETURN r
        """
        df_enrich = self.get_dataframe(query, nids=node_ids)
        return pd.merge(df, df_enrich, on="id", how="left")


__all__ = [
    "Biocyc",
    "BiocycDB",
    "CURRENCY_LABEL",
    "CURRENCY_METABOLITES",
    "EDGE_DESC_DICT",
]
