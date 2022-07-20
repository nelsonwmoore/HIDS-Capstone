"""
module docstring goes here
"""

import csv

import en_ner_bionlp13cg_md  # en_core_sci_lg another potential option
from bento_meta.objects import Concept, Predicate, Term
from nanoid import generate


def check_term_exists(tx, term: Term) -> bool:
    """If given Term node exists in database, returns True, otherwise returns False"""
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    result = tx.run("MATCH (t:term {value: $term_val, origin_name: $term_origin}) "
                    "RETURN t.value AS term", term_val=term.value, term_origin=term.origin_name)
    if [record["term"] for record in result]:
        return True
    else:
        return False

def get_concepts(tx, term: Term) -> list[Concept]:
    """Returns list of concepts represented by given Term"""
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    concepts = []
    result = tx.run("MATCH (t:term {value: $term_val, origin_name:$term_origin}) "
                    "-[:represents]->(c:concept) RETURN c.nanoid AS concept",
                    term_val=term.value, term_origin=term.origin_name)
    for record in result:
        concepts.append(record["concept"])
    return concepts

def create_term(tx, term: Term) -> None:
    """Adds given Term node to database"""
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    tx.run("MERGE (t:term {value: $term_val, origin_name:$term_origin})",
            term_val=term.value, term_origin=term.origin_name)
    print(f"Created new Term with value: {term.value} and origin: {term.origin_name}")

def make_nano():
    """Generates valid nanoid"""
    return generate(
        size=6,
        alphabet="abcdefghijkmnopqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ0123456789"
    )

def create_concept(tx, concept: Concept) -> None:
    """Adds given Concept node to database"""
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MERGE (n:concept {nanoid: $concept_nanoid})",
            concept_nanoid=concept.nanoid)
    print(f"Created Concept node with nanoid: {concept.nanoid}")

def create_represents_relationship(tx, term: Term, concept: Concept) -> None:
    """Adds represents relationship between given Term and Concept nodes"""
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (t:term {value: $term_val, origin_name: $term_origin}), "
            "(c:concept {nanoid: $concept_nanoid}) "
            "MERGE (t)-[r:represents]->(c)",
            term_val=term.value, term_origin=term.origin_name,
            concept_nanoid=concept.nanoid)
    print(f"Created represents relationship between Term with value: {term.value} "
        f"and origin: {term.origin_name} and Concept with nanoid: {concept.nanoid}")

def link_two_terms(tx, term_1: Term, term_2: Term) -> None:
    """
    Link two Term nodes in the MDB via a Concept node.

    This function takes two synonymous Terms as bento-meta objects and
    ensures they are present in the MDB and connected to each other via
    a Concept node and a 'represents' relationship.
    """
    if not (term_1.origin_name and term_1.value and
            term_2.origin_name and term_2.value):
        raise RuntimeError("args 'term_1' and 'term_2' must have both origin_name and value")

    term_1_exists = check_term_exists(tx, term_1)
    term_2_exists = check_term_exists(tx, term_2)

    if term_1_exists and term_2_exists:
        term_1_concepts = get_concepts(tx, term_1)
        term_2_concepts = get_concepts(tx, term_2)

        # Terms are already connected by a Concept
        if not set(term_1_concepts).isdisjoint(set(term_2_concepts)):
            existing_concept = set(term_1_concepts).intersection(set(term_2_concepts))
            print(f"Both terms are already connected via Concept {list(existing_concept)[0]}")

        # Terms are not already connected by a Concept
        elif set(term_1_concepts).isdisjoint(set(term_2_concepts)):
            # One of Terms already has a represents Concept
            if term_1_concepts:
                existing_concept = Concept()
                existing_concept.nanoid = term_1_concepts[0]
                create_represents_relationship(tx, term_2, existing_concept)
            elif term_2_concepts:
                existing_concept = Concept()
                existing_concept.nanoid = term_2_concepts[0]
                create_represents_relationship(tx, term_1, existing_concept)
            # Neither Term has an associated Concept
            else:
                new_concept = Concept()
                new_concept.nanoid = make_nano()
                create_concept(tx, new_concept)
                create_represents_relationship(tx, term_1, new_concept)
                create_represents_relationship(tx, term_2, new_concept)

    elif term_1_exists or term_2_exists:
        if term_1_exists:
            existing_term = term_1
            new_term = term_2
        else:
            existing_term = term_2
            new_term = term_1

        existing_term_concepts = get_concepts(tx, existing_term)

        if existing_term_concepts:
            create_term(tx, new_term)
            existing_concept = Concept()
            existing_concept.nanoid = existing_term_concepts[0]
            create_represents_relationship(tx, new_term, existing_concept)

        else:
            new_concept = Concept()
            new_concept.nanoid = make_nano()
            create_concept(tx, new_concept)
            create_term(tx, new_term)
            create_represents_relationship(tx, existing_term, new_concept)
            create_represents_relationship(tx, new_term, new_concept)

    else:
        create_term(tx, term_1)
        create_term(tx, term_2)
        new_concept = Concept()
        new_concept.nanoid = make_nano()
        create_concept(tx, new_concept)
        create_represents_relationship(tx, term_1, new_concept)
        create_represents_relationship(tx, term_2, new_concept)

def create_predicate(tx, predicate: Predicate) -> None:
    """Adds given Predicate node to database"""
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    valid_predicate_handles = ['exactMatch', 'closeMatch', 'broader', 'narrower', 'related']
    if predicate.handle not in valid_predicate_handles:
        raise RuntimeError(f"'handle' key must be one the following: {valid_predicate_handles}")
    tx.run("MERGE (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})",
            predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print(f"Created new Predicate with handle: {predicate.handle} and nanoid: {predicate.nanoid}")

def create_subject_relationship(tx, concept: Concept, predicate: Predicate) -> None:
    """Adds has_subject relationship to given Concept from given Predicate node"""
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_subject]->(c)",
        concept_nanoid=concept.nanoid,
        predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print("Created has_subject relationship between source Predicate with handle: "
        f"{predicate.handle} and nanoid: {predicate.nanoid} and destination Concept "
        f"with nanoid: {concept.nanoid}")

def create_object_relationship(tx, concept: Concept, predicate: Predicate) -> None:
    """Adds has_subject relationship to given Concept from given Predicate node"""
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("MATCH (c:concept {nanoid: $concept_nanoid}), "
        "(p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid}) "
        "MERGE (p)-[:has_object]->(c)",
        concept_nanoid=concept.nanoid,
        predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print("Created has_object relationship between source Predicate with handle: "
        f"{predicate.handle} and nanoid: {predicate.nanoid} and destination Concept "
        f"with nanoid: {concept.nanoid}")

def get_terms(tx, concept: Concept) -> list[Term]:
    """Returns list of Term nodes representing given Concept"""
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    terms = []
    result = tx.run("MATCH (t:term)-[:represents]->(c:concept {nanoid: $concept_nanoid}) "
                    "RETURN t.value AS term_val, t.origin_name AS term_origin",
                    concept_nanoid=concept.nanoid)
    for record in result:
        terms.append(Term({"value": record["term_val"], "origin_name": record["term_origin"]}))
    return terms

def get_predicates(tx, concept: Concept) -> list[list]:
    """Returns list of Predicate nodes with relationship to given Concept"""
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    preds = []
    result = tx.run("MATCH (p:predicate)-[r]->(c:concept {nanoid: $concept_nanoid}) "
                    "RETURN p.handle AS pred_handle, p.nanoid AS pred_nano, type(r) as edge",
                    concept_nanoid=concept.nanoid)
    for record in result:
        preds.append([Predicate({"handle": record["pred_handle"], "nanoid": record["pred_nano"]}),
                    record["edge"]])
    return preds

def detach_delete_predicate(tx, predicate: Predicate) -> None:
    """Remove given Predicate node from database"""
    if not (predicate.handle and predicate.nanoid):
        raise RuntimeError("arg 'predicate' must have both handle and nanoid")
    tx.run("match (p:predicate {handle: $predicate_handle, nanoid: $predicate_nanoid})"
            "detach delete p", predicate_handle=predicate.handle, predicate_nanoid=predicate.nanoid)
    print(f"Removed Predicate node with handle: {predicate.handle} and nanoid: {predicate.nanoid}")

def detach_delete_concept(tx, concept: Concept) -> None:
    """Remove given Concept node from database"""
    if not concept.nanoid:
        raise RuntimeError("arg 'concept' must have nanoid")
    tx.run("match (c:concept {nanoid: $nanoid})"
            "detach delete c", nanoid=concept.nanoid)
    print(f"Removed Concept node with nanoid: {concept.nanoid}")

def detach_delete_term(tx, term: Term) -> None:
    """Remove given Term node from database"""
    if not (term.origin_name and term.value):
        raise RuntimeError("arg 'term' must have both origin_name and value")
    tx.run("match (t:term {value: $term_val, origin_name: $term_origin})"
            "detach delete t", term_val=term.value, term_origin=term.origin_name)
    print(f"Removed Term node with value: {term.value} and origin: {term.origin_name}")

def link_concepts_to_predicate(tx, concept_1: Concept, concept_2: Concept,
                                predicate_handle: str = "exactMatch") -> None:
    """
    Links two synonymous Concepts via a Predicate

    This function takes two synonymous Concepts as objects and links
    them via a Predicate node and has_subject and has_object relationships.
    """

    if not (concept_1.nanoid and concept_2.nanoid):
        raise RuntimeError("args 'concept_1' and 'concept_2' must have nanoid")

    # create predicate
    new_predicate = Predicate()
    new_predicate.handle = predicate_handle
    new_predicate.nanoid = make_nano()
    create_predicate(tx, new_predicate)

    # link concepts to predicate via subject & object relationships
    create_subject_relationship(tx, concept_1, new_predicate)
    create_object_relationship(tx, concept_2, new_predicate)

def merge_two_concepts(tx, concept_1: Concept, concept_2: Concept) -> None:
    """
    Combine two synonymous Concepts into a single Concept.

    This function takes two synonymous Concept as bento-meta objects and
    merges them into a single Concept along with any connected Terms and Predicates.
    """
    if not (concept_1.nanoid and concept_2.nanoid):
        raise RuntimeError("args 'concept_1' and 'concept_2' must have nanoid")

    # get list of all terms connected to concept 2
    c2_terms = get_terms(tx, concept_2)
    # get list of all predicates connected to concept 2
    c2_preds = get_predicates(tx, concept_2)
    # delete concept 2
    detach_delete_concept(tx, concept_2)
    # connect terms from deleted (c2) to remaining concept (c1)
    for term in c2_terms:
        create_represents_relationship(tx, term, concept_1)
    # connect predicates from deleted (c2) to remaining concept (c1)
    for pred in c2_preds:
        c2_edge = pred[1]
        c2_pred = Predicate({"handle": pred[0].handle, "nanoid": pred[0].nanoid})
        if c2_edge == "has_object":
            create_object_relationship(tx, concept_1, c2_pred)
        elif c2_edge == "has_subject":
            create_subject_relationship(tx, concept_1, c2_pred)

def get_term_synonyms(tx, term: Term, threshhold: float = 0.8) -> list[dict]:
    """Returns list of dicts representing Term nodes synonymous to given Term"""
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
    """Given a list of synonymous Terms as dicts, outputs to CSV file at given output path"""
    with open(output_path, "w", encoding="utf8", newline="") as output_file:
        dict_writer = csv.DictWriter(output_file,
                                    fieldnames=input_data[0].keys())
        dict_writer.writeheader()
        dict_writer.writerows(input_data)

def link_term_synonyms_csv(tx, term: Term, csv_path: str) -> None:
    """Given a CSV of syonymous Terms, links each via a Concept node to given Term"""
    with open(csv_path, encoding="UTF-8") as csvfile:
        synonym_reader = csv.reader(csvfile)
        for line in synonym_reader:
            if line[3] == "1":
                synonym = Term()
                synonym.value = line[0]
                synonym.origin_name = line[1]
                link_two_terms(tx, term, synonym)
