from neo4j import GraphDatabase, basic_auth
from nanoid import generate
import csv
import spacy
import en_ner_bionlp13cg_md #en_core_sci_lg another potential option
from bento_meta.objects import Term, Concept, Predicate
from bento_meta.mdb import MDB

def check_term_exists(tx, term: object) -> bool:
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")    
    result = tx.run("MATCH (t:term {value: $term_val, origin_name: $term_origin}) "
                    "RETURN t.value AS term", term_val=term.value, term_origin=term.origin_name)
    if [record["term"] for record in result]:
        return True
    else:
        return False

def get_concept(tx, term: object) -> list[object]:
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    concepts = []
    result = tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin})-[:represents]->(c:concept) "
                    "RETURN c.nanoid AS concept", term_val=term.value, term_origin=term.origin_name)
    for record in result:
        concepts.append(record["concept"])
    return concepts

def create_term(tx, term: object) -> None:
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    tx.run("MERGE (t:term {value: $term_val, origin_name:$term_origin})",
            term_val=term.value, term_origin=term.origin_name)
    print(f"Created new Term with value: {term.value} and origin: {term.origin_name}")

def make_nano():
    return generate(
        size=6,
        alphabet="abcdefghijkmnopqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ0123456789"
    )

def create_concept(tx, concept: object) -> None:
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MERGE (n:concept {nanoid: $concept_nanoid})", 
            concept_nanoid=concept.nanoid)
    print(f"Created new Concept with nanoid: {concept.nanoid}")

def create_represents_relationship(tx, term: object, concept: object) -> None:
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin}), "
            "(c:concept {nanoid: $concept_nanoid}) "
            "MERGE (t)-[r:represents]->(c)", 
            term_val=term.value, term_origin=term.origin_name, 
            concept_nanoid=concept.nanoid)
    print(f"Term with value: {term.value} and origin: {term.origin_name} now represents Concept with nanoid: {concept.nanoid}")

def link_two_terms(term_1: object, term_2: object) -> None:
    """
    Link two Term nodes in the MDB via a Concept node.

    This function takes two synonymous Terms as bento-meta objects and 
    ensures they are present in the MDB and connected to each other via 
    a Concept node and a 'represents' relationship.
    """
    if not (term_1.origin_name and term_1.value and
            term_2.origin_name and term_2.value):
        raise RuntimeError("args 'term_1' and 'term_2' must have both origin_name and value")

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
                new_concept = Concept()
                new_concept.nanoid = make_nano()
                session.write_transaction(create_concept, new_concept)
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
                existing_concept = Concept()
                existing_concept.nanoid = existing_term_concepts[0]
                session.write_transaction(create_represents_relationship, new_term, existing_concept)

            else:      
                new_concept = Concept()
                new_concept.nanoid = make_nano()
                session.write_transaction(create_concept, new_concept)
                session.write_transaction(create_term, new_term)
                session.write_transaction(create_represents_relationship, existing_term, new_concept)
                session.write_transaction(create_represents_relationship, new_term, new_concept)

        else:
            session.write_transaction(create_term, term_1)
            session.write_transaction(create_term, term_2)
            new_concept = Concept()
            new_concept.nanoid = make_nano()
            session.write_transaction(create_concept, new_concept)
            session.write_transaction(create_represents_relationship, term_1, new_concept)
            session.write_transaction(create_represents_relationship, term_2, new_concept)
    
    driver.close()

def create_predicate(tx, predicate: object) -> None:
    """Creates a predicate node using a HandledPredicate object (for now)"""
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    valid_predicate_handles = ['exactMatch', 'closeMatch', 'broader', 'narrower', 'related']
    if predicate.handle not in valid_predicate_handles:
        raise RuntimeError(f"'handle' key must be one the following: {valid_predicate_handles}")
    tx.run("MERGE (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})", 
            predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print(f"Created new Predicate with handle: {predicate.handle} and nanoid: {predicate.nanoid}")

def create_subject_relationship(tx, concept: object, predicate: object) -> None:
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_subject]->(c)", 
        concept_nanoid=concept.nanoid, 
        predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print(f"Created has_subject relationship between source Predicate with handle: "
        f"{predicate.handle} and nanoid: {predicate.nanoid} and destination Concept "
        f"with nanoid: {concept.nanoid}")

def create_object_relationship(tx, concept: object, predicate: object) -> None:
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_object]->(c)", 
        concept_nanoid=concept.nanoid, 
        predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print(f"Created has_object relationship between source Predicate with handle: "
        f"{predicate.handle} and nanoid: {predicate.nanoid} and destination Concept "
        f"with nanoid: {concept.nanoid}")

def get_terms(tx, concept: object) -> list[object]:
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    terms = []
    result = tx.run("MATCH (t:term)-[:represents]->(c:concept {nanoid: $concept_nanoid}) "
                    "RETURN t.value AS term_val, t.origin_name AS term_origin",
                    concept_nanoid=concept.nanoid)
    for record in result:
        terms.append(Term({"value": record["term_val"], "origin_name": record["term_origin"]}))
    return terms

def detach_delete_predicate(tx, predicate: object) -> None:
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    tx.run("match (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})"
            "detach delete p", predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)

def detach_delete_concept(tx, concept: object) -> None:
    if not (concept.nanoid):
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("match (c:concept {nanoid: $nanoid})"
            "detach delete c", nanoid=concept.nanoid)

def link_concepts_to_predicate(concept_1: object, concept_2: object, predicate_handle: str = "exactMatch") -> None:
    """
    Links two synonymous Concepts via a Predicate 

    This function takes two synonymous Concepts as objects and links 
    them via a Predicate node and has_subject and has_object relationships.
    """
    
    if not (concept_1.nanoid and concept_2.nanoid):
        raise RuntimeError("args 'concept_1' and 'concept_2' must have nanoid")
    
    with driver.session() as session:

        # create predicate
        new_predicate = Predicate()
        new_predicate.handle = predicate_handle
        new_predicate.nanoid = make_nano()
        session.write_transaction(create_predicate, new_predicate)

        # link concepts to predicate via subject & object relationships
        session.write_transaction(create_subject_relationship, concept_1, new_predicate)
        session.write_transaction(create_object_relationship, concept_2, new_predicate)

    driver.close()

def merge_two_concepts(concept_1: object, concept_2: object) -> None:
    """
    Combine two synonymous Concepts into a single Concept.

    This function takes two synonymous Concept as objects and
    merges them into a single Concept.
    """
    if not (concept_1.nanoid and concept_2.nanoid):
        raise RuntimeError("args 'concept_1' and 'concept_2' must have nanoid")

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

def get_term_synonyms(tx, term: object, threshhold: float = 0.8) -> list[dict]:
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")  
    
    # load spaCy NER model
    nlp = en_ner_bionlp13cg_md.load()

    synonyms = []
    result = tx.run("MATCH (t:term) "
                    "RETURN t.value AS term_val, t.origin_name AS term_origin")
    for record in result:
        # calculate similarity between each Term and input Term
        term_1 = nlp(term.value)
        term_2 = nlp(str(record["term_val"]))
        similarity = term_1.similarity(term_2)
        # if similarity threshold met, add to list of potential synonyms
        if similarity >= threshhold:
            synonym = {
                "value": record["term_val"],
                "origin_name": record["term_origin"],
                "similarity": similarity,
                "valid_synonym": 0 # 0 for now when downloading; mark 1 if synonym when uploading
            }
            synonyms.append(synonym)
    synonyms_sorted = sorted(synonyms, key=lambda d: d["similarity"], reverse=True)
    return synonyms_sorted

def potential_synonyms_to_csv(input_data: list[dict], output_path: str) -> None:
    with open(output_path, "w", encoding="utf8", newline="") as output_file:
        dict_writer = csv.DictWriter(output_file,
                                    fieldnames=input_data[0].keys())
        dict_writer.writeheader()
        dict_writer.writerows(input_data)