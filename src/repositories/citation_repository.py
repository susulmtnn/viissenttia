import json
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from config import db
from util import citation_data_to_class, sql_insert_writer, get_citation_types


def get_citations():
    """
    Get citations from database
    :return: list of citation objects
    """
    citation_classes=[]
    for citation_type in get_citation_types():
        try:
            citations = db.session.execute(
                text(
                    f"""
                    SELECT * FROM citation_base 
                    INNER JOIN {citation_type}
                    ON citation_base.id = {citation_type}.citation_id
                    """
                )
            ).mappings()

            citation_classes.extend([result for c in citations if (result := citation_data_to_class(dict(c)))])
        except SQLAlchemyError:
            pass


    return sorted(
        citation_classes,
        key=lambda x: x.created_at,
        reverse=True,
    )


def create_citation(citation_class):
    """
    Insert citation into database.
    :return: True if successful, False if not
    """
    try:
        # Insert to citation_base
        citation_base_sql = text(
            """
            INSERT INTO citation_base (key, type, created_at)
            VALUES (:key, :type, :created_at)
            RETURNING id
            """
        )
        result = db.session.execute(
            citation_base_sql,
            {
                "key": citation_class.key,
                "type": citation_class.type,
                "created_at": citation_class.created_at,
            },
        )
        citation_base_id = result.fetchone()[0]

        citation_dict = vars(citation_class)
        citation_dict["citation_id"] = citation_base_id
        citation_dict["author"] = json.dumps(citation_class.author)
        if hasattr(citation_class, "editor"):
            citation_dict["editor"] = json.dumps(citation_class.editor)

        sql_command = text(sql_insert_writer(citation_class.type, citation_dict))

        db.session.execute(
            sql_command,
            citation_dict,
        )

        db.session.commit()
        return True

    except DataError as e:  # Catches invalid values
        db.session.rollback()
        print(f"Data error: {e}")
        return False
    except IntegrityError as e:  # Catches missing keys and other constraint violations
        db.session.rollback()
        print(f"Integrity error: {e}")
        return False
    except SQLAlchemyError as e:  # Catches other database errors
        db.session.rollback()
        print(f"Database error: {e}")
        return False
    except Exception as e:
        db.session.rollback()
        print(f"Unexpected error: {e}")
        # Raise fatal error if some other exception is encountered
        raise

def delete_citation(citation_id):
    try:
        citation_type = get_citation_type(citation_id)  # Hae sitaatin tyyppi ID:n perusteella
        if citation_type:
            delete_sql = text(f"DELETE FROM {citation_type} WHERE citation_id = :citation_id")
            db.session.execute(delete_sql, {"citation_id": citation_id})

        delete_base_sql = text("DELETE FROM citation_base WHERE id = :citation_id")
        db.session.execute(delete_base_sql, {"citation_id": citation_id})

        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Database error while deleting citation: {e}")
        return False

def get_citation_type(citation_id):
    try:
        result = db.session.execute(
            text("SELECT type FROM citation_base WHERE id = :citation_id"),
            {"citation_id": citation_id}
        ).fetchone()
        return result[0] if result else None
    except SQLAlchemyError as e:
        print(f"Database error while getting citation type: {e}")
        return None
