from neo4j import GraphDatabase, basic_auth
from nanoid import generate

def check_term_exists(tx, term):
    if not ("origin_name" in term and "value" in term):
        raise RuntimeError("arg 'term' must contain both origin_name and value keys")    
    result = tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin}) "
                    "RETURN t.value AS term", term_val=term["value"], term_origin=term["origin_name"])
    if [record["term"] for record in result]:
        return True
    else:
        return False

def get_concept(tx, term: dict):
    if not ("origin_name" in term and "value" in term):
        raise RuntimeError("arg 'term' must contain both origin_name and value keys")
    concepts = []
    result = tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin})-[:represents]->(c:concept) "
                    "RETURN c.nanoid AS concept", term_val=term["value"], term_origin=term["origin_name"])
    for record in result:
        concepts.append(record["concept"])
    return concepts

def create_term(tx, term: dict):
    if not ("origin_name" in term and "value" in term):
        raise RuntimeError("arg 'term' must contain both origin_name and value keys")
    tx.run("MERGE (t:term {value: $term_val, origin_name:$term_origin})",
            term_val=term["value"], term_origin=term["origin_name"])
    print(f"Created new Term with value: {term['value']} and origin: term['origin_name']")

def make_nano():
    return generate(
        size=6,
        alphabet="abcdefghijkmnopqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ0123456789"
    )

def generate_unique_nanoid(tx):
    nanoid = make_nano()
    result = tx.run("MATCH (n {nanoid: $nanoid}) "
                    "RETURN n.nanoid", nanoid=nanoid)
    if not [record["n.nanoid"] for record in result]:
        return nanoid
    else:
        generate_unique_nanoid(tx)

def create_concept(tx, concept: dict):
    if not ("nanoid" in concept):
        raise RuntimeError("arg 'concept' must contain nanoid key")
    tx.run("MERGE (n:concept {nanoid: $concept_nanoid})", 
            concept_nanoid=concept["nanoid"])
    print(f"Created new Concept with nanoid: {concept['nanoid']}")

def create_represents_relationship(tx, term: dict, concept: dict):
        if not ("origin_name" in term and "value" in term):
                raise RuntimeError("arg 'term' must contain both origin_name and value keys")
        if not ("nanoid" in concept):
                raise RuntimeError("arg 'concept' must contain nanoid key")
        tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin}), "
                "(c:concept {nanoid: $concept_nanoid}) "
                "MERGE (t)-[r:represents]->(c) ", 
                term_val=term["value"], term_origin=term["origin_name"], 
                concept_nanoid=concept["nanoid"])
        print(f"Term with value: {term['value']} and origin: {term['origin_name']} now represents Concept with nanoid: {concept['nanoid']}")

def link_two_terms(term_1: dict, term_2: dict) -> None:
    """
    Link two Term nodes in the MDB via a Concept node.

    This function takes two synonymous Terms as dictionaries and 
    ensures they are present in the MDB and connected to each other via 
    a Concept node and a 'represents' relationship.
    """
    if not ("origin_name" in term_1 and "value" in term_1 and
            "origin_name" in term_2 and "value" in term_2):
        raise RuntimeError("args 'term_1' and 'term_2' must contain both origin_name and value keys")

    with driver.session() as session:

        term_1_exists = session.read_transaction(check_term_exists, term_1)
        term_2_exists = session.read_transaction(check_term_exists, term_2)

        if term_1_exists and term_2_exists:
            term_1_concepts = session.read_transaction(get_concept, term_1)
            term_2_concepts = session.read_transaction(get_concept, term_2)
            
            # Terms are already connected by a Concept
            if not set(term_1_concepts).isdisjoint(set(term_2_concepts)):
                existing_concept = set(term_1_concepts).intersection(set(term_2_concepts))             
                print(f"Both terms are already connected via Concept {list(existing_concept)[0]}")

            # Terms are not already connected by a Concept
            elif set(term_1_concepts).isdisjoint(set(term_2_concepts)):                               
                new_nanoid = session.read_transaction(generate_unique_nanoid)
                new_concept = {"nanoid": new_nanoid}
                session.write_transaction(create_concept, {"nanoid": new_nanoid})
                session.write_transaction(create_represents_relationship, term_1, new_concept)
                session.write_transaction(create_represents_relationship, term_2, new_concept)

        elif term_1_exists or term_2_exists:
            if term_1_exists:
                existing_term = term_1
                new_term = term_2
            else:
                existing_term = term_2
                new_term = term_1

            existing_term_concepts = session.read_transaction(get_concept, existing_term)

            if existing_term_concepts:                
                session.write_transaction(create_term, new_term)
                existing_concept_nanoid = existing_term_concepts[0]
                existing_concept = {"nanoid": existing_concept_nanoid}
                session.write_transaction(create_represents_relationship, new_term, existing_concept)

            else:      
                new_nanoid = session.read_transaction(generate_unique_nanoid)
                new_concept = {"nanoid": new_nanoid}
                session.write_transaction(create_concept, new_concept)
                session.write_transaction(create_term, new_term)
                session.write_transaction(create_represents_relationship, existing_term, new_concept)
                session.write_transaction(create_represents_relationship, new_term, new_concept)

        else:
            session.write_transaction(create_term, term_1)
            session.write_transaction(create_term, term_2)
            new_nanoid = session.read_transaction(generate_unique_nanoid)
            session.write_transaction(create_concept, new_nanoid)
            session.write_transaction(create_represents_relationship, term_1, new_nanoid)
            session.write_transaction(create_represents_relationship, term_2, new_nanoid)
    
    driver.close()

def create_predicate(tx, predicate: dict):
    if not ("handle" in predicate and "nanoid" in predicate):
            raise RuntimeError("arg 'predicate' must contain both handle and nanoid keys")
    tx.run("MERGE (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})", 
            predicate_handle=predicate["handle"], predicate_nanoid=predicate["nanoid"])
    print(f"Created new Predicate with handle: {predicate['handle']} and nanoid: {predicate['nanoid']}")

def create_subject_relationship(tx, concept: dict, predicate: dict):
    if not ("handle" in predicate and "nanoid" in predicate):
        raise RuntimeError("arg 'predicate' must contain both handle and nanoid keys")
    if not ("nanoid" in concept):
        raise RuntimeError("arg 'concept' must contain nanoid key")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_subject]->(c)", 
        concept_nanoid=concept["nanoid"], 
        predicate_handle=predicate["handle"], predicate_nanoid=predicate["nanoid"])
    print(f"Created has_subject relationship between source Predicate with handle: "
        f"{predicate['handle']} and nanoid: {predicate['nanoid']} and destination Concept "
        f"with nanoid: {concept['nanoid']}")

def create_object_relationship(tx, concept: dict, predicate: dict):
    if not ("handle" in predicate and "nanoid" in predicate):
        raise RuntimeError("arg 'predicate' must contain both handle and nanoid keys")
    if not ("nanoid" in concept):
        raise RuntimeError("arg 'concept' must contain nanoid key")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_object]->(c)", 
        concept_nanoid=concept["nanoid"], 
        predicate_handle=predicate["handle"], predicate_nanoid=predicate["nanoid"])
    print(f"Created has_object relationship between source Predicate with handle: "
        f"{predicate['handle']} and nanoid: {predicate['nanoid']} and destination Concept "
        f"with nanoid: {concept['nanoid']}")

def get_terms(tx, concept: dict):
    if not ("nanoid" in concept):
        raise RuntimeError("arg 'concept' must contain nanoid key")
    terms = []
    result = tx.run("MATCH (t:term)-[:represents]->(c:concept {nanoid: $concept_nanoid}) "
                    "RETURN t.value AS term_val, t.origin_name AS term_origin",
                    concept_nanoid=concept["nanoid"])
    for record in result:
        terms.append({"value": record["term_val"], "origin_name": record["term_origin"]})
    return terms

def detach_delete_predicate(tx, predicate: dict):
    if not ("handle" in predicate and "nanoid" in predicate):
        raise RuntimeError("arg 'predicate' must contain both handle and nanoid keys")
    tx.run("match (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})"
            "detach delete p", predicate_handle=predicate["handle"], predicate_nanoid=predicate["nanoid"])

def detach_delete_concept(tx, concept: dict):
    if not ("nanoid" in concept):
        raise RuntimeError("arg 'concept' must contain nanoid key")
    tx.run("match (c:concept {nanoid: $nanoid})"
            "detach delete c", nanoid=concept["nanoid"])

def link_concepts_to_predicate(concept_1: dict, concept_2: dict, predicate_handle="exactMatch") -> None:
    """
    Links two synonymous Concepts via a Predicate 

    This function takes two synonymous Concepts as dictionaries and links 
    them via a Predicate node and has_subject and has_object relationships.
    """
    
    if not ("nanoid" in concept_1 and "nanoid" in concept_2):
        raise RuntimeError("args 'concept_1' and 'concept_2' must contain nanoid key")
    
    with driver.session() as session:

        # create predicate
        new_predicate_nanoid = session.read_transaction(generate_unique_nanoid)
        new_predicate = {"handle": predicate_handle, "nanoid": new_predicate_nanoid}
        session.write_transaction(create_predicate, new_predicate)

        # link concepts to predicate via subject & object relationships
        session.write_transaction(create_subject_relationship, concept_1, new_predicate)
        session.write_transaction(create_object_relationship, concept_2, new_predicate)

    driver.close()

def merge_two_concepts(concept_1: dict, concept_2: dict) -> None:
    """
    Combine two synonymous Concepts into a single Concept

    This function takes two synonymous Concept as dictionaries and
    merges them into a single Concept.
    """

    if not ("nanoid" in concept_1 and "nanoid" in concept_2):
        raise RuntimeError("args 'concept_1' and 'concept_2' must contain nanoid key")

    with driver.session() as session:
        
        # get list of all terms connected to concept 2
        c2_terms = session.read_transaction(get_terms, concept_2)

        # get list of all predicates connected to concept 2 (wip)

        # delete concept 2
        session.write_transaction(detach_delete_concept, concept_2)

        # connect terms from deleted concept to remaining concept
        for term in c2_terms:
            session.write_transaction(create_represents_relationship, term, concept_1)

    driver.close()