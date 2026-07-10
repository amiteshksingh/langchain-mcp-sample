# app/document_loader.py

from pathlib import Path
import json

from langchain_core.documents import Document


def load_source_documents(data_dir: str) -> list[Document]:

    data_path = Path(data_dir)

    metadata_file = data_path / "metadata.json"

    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_file}"
        )

    metadata_map = json.loads(
        metadata_file.read_text(encoding="utf-8")
    )

    documents = []

    for txt_file in data_path.glob("*.txt"):

        text = txt_file.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            continue

        metadata = metadata_map.get(
            txt_file.name,
            {}
        )

        document = Document(
            page_content=text,
            metadata={
                "source": str(txt_file),
                "fileName": txt_file.name,
                **metadata
            }
        )

        documents.append(document)

    return documents