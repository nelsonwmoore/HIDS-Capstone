from neo4j import GraphDatabase, basic_auth
import random
import string

def check_term_exists(tx, term_val):
    result = tx.run("MATCH (t:term {value: $term_val}) "
                    "RETURN t.value AS term", term_val=term_val)
    if [record["term"] for record in result]:
        return True
    else:
        return False

def get_concept(tx, term_val):
    concepts = []
    result = tx.run("MATCH (t:term {value: $term_val})-[:represents]->(c:concept) "
                    "RETURN c.nanoid AS concept", term_val=term_val)
    for record in result:
        concepts.append(record["concept"])
    return concepts

def create_term(tx, term_val):
    tx.run("MERGE (n:term {value: $term_val, origin_name: 'NDC'})",
            term_val=term_val)
    print(f"Created new Term with value: {term_val}")

def generate_nanoid():
    valid_chars = string.ascii_letters + string.digits
    nanoid = ''.join(random.choice(valid_chars) for i in range(6))
    return nanoid

def generate_unique_nanoid(tx):
    nanoid = generate_nanoid()
    result = tx.run("MATCH (n {nanoid: $nanoid}) "
                    "RETURN n.nanoid", nanoid=nanoid)
    if not [record["n.nanoid"] for record in result]:
        #print(nanoid)
        return nanoid
    else:
        generate_unique_nanoid(tx)

def create_concept(tx, concept_nanoid):    
    tx.run("MERGE (n:concept {nanoid: $concept_nanoid})", 
            concept_nanoid=concept_nanoid)
    print(f"Created new Concept with nanoid: {concept_nanoid}")

# link term and concept
def create_represents_relationship(tx, term_val, concept_nanoid):
        tx.run("MATCH (t:term {value: $term_val}), "
                "(c:concept {nanoid: $concept_nanoid}) "
                "MERGE (t)-[r:represents]->(c) ", 
                term_val=term_val, 
                concept_nanoid=concept_nanoid)
        print(f"{term_val} Term now represents {concept_nanoid} Concept")

def link_two_terms(term_val_1: str, term_val_2: str) -> None:
    """
    Link two Term nodes in the MDB via a Concept node.

    This function takes two synonymous Term values as input strings and 
    ensures they are present in the MDB and connected to each other via 
    a Concept node and a 'represents' relationship.
    """

    with driver.session() as session:

        term_1_exists = session.read_transaction(check_term_exists, term_val_1)
        term_2_exists = session.read_transaction(check_term_exists, term_val_2)

        if term_1_exists and term_2_exists:
            term_1_concepts = session.read_transaction(get_concept, term_val_1)
            term_2_concepts = session.read_transaction(get_concept, term_val_2)
            
            # Terms are already connected by a Concept
            if not set(term_1_concepts).isdisjoint(set(term_2_concepts)):
                existing_concept = set(term_1_concepts).intersection(set(term_2_concepts))             
                print(f"{term_val_1} and {term_val_2} are already connected via Concept {list(existing_concept)[0]}")

            # Terms are not already connected by a Concept
            elif set(term_1_concepts).isdisjoint(set(term_2_concepts)):                               
                new_nanoid = session.read_transaction(generate_unique_nanoid)
                session.write_transaction(create_concept, new_nanoid)
                session.write_transaction(create_represents_relationship, term_val_1, new_nanoid)
                session.write_transaction(create_represents_relationship, term_val_2, new_nanoid)

        elif term_1_exists or term_2_exists:
            if term_1_exists:
                existing_term = term_val_1
                new_term = term_val_2
            else:
                existing_term = term_val_2
                new_term = term_val_1

            existing_term_concepts = session.read_transaction(get_concept, existing_term)

            if existing_term_concepts:                
                session.write_transaction(create_term, new_term)
                existing_concept_nanoid = existing_term_concepts[0]
                session.write_transaction(create_represents_relationship, new_term, existing_concept_nanoid)

            else:      
                new_nanoid = session.read_transaction(generate_unique_nanoid)
                session.write_transaction(create_concept, new_nanoid)
                session.write_transaction(create_term, new_term)
                session.write_transaction(create_represents_relationship, existing_term, new_nanoid)
                session.write_transaction(create_represents_relationship, new_term, new_nanoid)

        else:
            session.write_transaction(create_term, term_val_1)
            session.write_transaction(create_term, term_val_2)
            new_nanoid = session.read_transaction(generate_unique_nanoid)
            session.write_transaction(create_concept, new_nanoid)
            session.write_transaction(create_represents_relationship, term_val_1, new_nanoid)
            session.write_transaction(create_represents_relationship, term_val_2, new_nanoid)
    
    driver.close()

def create_predicate(tx, predicate_nanoid, predicate_handle):    
        tx.run("MERGE (n:predicate {nanoid: $predicate_nanoid, handle: $predicate_handle})", 
                predicate_nanoid=predicate_nanoid, predicate_handle=predicate_handle)
        print(f"Created new Predicate with nanoid: {predicate_nanoid} and handle: {predicate_handle}")

def create_subject_relationship(tx, concept_nanoid, predicate_nanoid):
        tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
                "(p:predicate {nanoid: $predicate_nanoid}) "
                "MERGE (p)-[:has_subject]->(c)", 
                concept_nanoid=concept_nanoid, 
                predicate_nanoid=predicate_nanoid)
        print(f"Created has_subject relationship between source Predicate: {predicate_nanoid} and destination Concept: {concept_nanoid}")

def create_object_relationship(tx, concept_nanoid, predicate_nanoid):
        tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
                "(p:predicate {nanoid: $predicate_nanoid}) "
                "MERGE (p)-[:has_object]->(c)", 
                concept_nanoid=concept_nanoid, 
                predicate_nanoid=predicate_nanoid)
        print(f"Created has_object relationship between source Predicate: {predicate_nanoid} and destination Concept: {concept_nanoid}")

def get_terms(tx, concept_nanoid):
    terms = []
    result = tx.run("MATCH (t:term)-[:represents]->(c:concept {nanoid: $concept_nanoid}) "
                    "RETURN t.nanoid AS term", concept_nanoid=concept_nanoid)
    for record in result:
        terms.append(record["term"])
    return terms

def detach_delete_predicate(tx, nanoid):
    tx.run("match (p:predicate {nanoid: $nanoid})"
            "detach delete p", nanoid=nanoid)

def detach_delete_concept(tx, nanoid):
    tx.run("match (c:concept {nanoid: $nanoid})"
            "detach delete c", nanoid=nanoid)

def create_term_from_nanoid(tx, term_val, term_nanoid):
        tx.run("MERGE (n:term {origin_name: 'NDC', "
                "nanoid: $term_nanoid})", 
                term_val=term_val, term_nanoid=term_nanoid)
        print(f"Created new Term with value: {term_val} and nanoid: {term_nanoid}")

def create_represents_relationship_from_nanoid(tx, term_nanoid, concept_nanoid):
        tx.run("MATCH (t:term {nanoid: $term_nanoid}), "
                "(c:concept {nanoid: $concept_nanoid}) "
                "MERGE (t)-[r:represents]->(c) ", 
                term_nanoid=term_nanoid,
                concept_nanoid=concept_nanoid)
        print(f"Term with nanoid:{term_nanoid} now represents Concept: {concept_nanoid}")

def link_concepts_to_predicate(concept_id_1: str, concept_id_2: str, predicate_handle="exactMatch") -> None:
    """
    Links two synonymous Concepts via a Predicate 

    This function takes two synonymous Concept nanoids as input strings and links 
    them via a Predicate node and has_subject and has_object relationships. The 
    predicate_handle parameter is defaulted to "exactMatch" but other similar
    SKOS terms include "relatedMatch" and "closeMatch".
    """
    
    with driver.session() as session:

        # create predicate
        new_predicate_nanoid = session.read_transaction(generate_unique_nanoid)
        session.write_transaction(create_predicate, new_predicate_nanoid, predicate_handle)

        # link concepts to predicate via subject & object relationships
        session.write_transaction(create_subject_relationship, concept_id_1, new_predicate_nanoid)
        session.write_transaction(create_object_relationship, concept_id_2, new_predicate_nanoid)

    driver.close()

def merge_two_concepts(concept_id_1: str, concept_id_2: str) -> None:
    """
    Combine two synonymous Concepts into a single Concept

    This function takes two synonymous Concept nanoids as input strings and
    merges them into a single Concept.
    """

    with driver.session() as session:
        
        # get list of all terms connected to concept 2
        c2_terms = session.read_transaction(get_terms, concept_id_2)

        # delete concept 2
        session.write_transaction(detach_delete_concept, concept_id_2)

        # connect terms from deleted concept to remaining concept
        for term_id in c2_terms:
            session.write_transaction(create_represents_relationship, term_id, concept_id_1)

    driver.close()