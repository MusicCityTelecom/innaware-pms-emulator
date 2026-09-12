"""Read-only optional validation against an operator-supplied CMND WAR.

Requires lxml in the validation environment only. Vendor files stay in the
archive and are not extracted, copied, changed or published.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import posixpath
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from innaware_pms_emulator.protocols.cmnd import CmndHtngAdapter, SOAP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("war", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.war) as archive:
        # libxml2 ignores later imports of a namespace already imported by a
        # sibling XSD. The distributed HTNG set imports multiple OTA entry
        # points. Assemble their reachable declarations in memory, retaining
        # the original namespace contexts; never modify the reference files.
        documents = {}

        def collect(name):
            if name in documents:
                return
            document = etree.fromstring(archive.read(name))
            documents[name] = document
            for node in document:
                location = node.get("schemaLocation")
                if location:
                    collect(posixpath.normpath(posixpath.join(posixpath.dirname(name), location)))

        for suffix in ("CheckIn", "CheckOut"):
            collect(f"WEB-INF/classes/HTNG/messages/HTNG_Hotel{suffix}NotifRQ.xsd")
        groups = {}
        seen = set()
        for document in documents.values():
            namespace = document.get("targetNamespace")
            if namespace not in groups:
                groups[namespace] = etree.Element(document.tag, dict(document.attrib), nsmap=document.nsmap)
            for node in document:
                if node.get("name"):
                    key = namespace, node.tag, node.get("name")
                    if key not in seen:
                        groups[namespace].append(deepcopy(node))
                        seen.add(key)
        xs = "http://www.w3.org/2001/XMLSchema"
        for namespace, document in groups.items():
            for other in groups:
                if other != namespace:
                    document.insert(0, etree.Element(f"{{{xs}}}import", namespace=other, schemaLocation=other))

        class Resolver(etree.Resolver):
            def resolve(self, url, pubid, context):
                if url not in groups:
                    raise ValueError("Reference resolution outside the in-memory schema set is forbidden")
                return self.resolve_string(etree.tostring(groups[url]), context, base_url=url)

        xml_parser = etree.XMLParser(no_network=True, resolve_entities=False)
        xml_parser.resolvers.add(Resolver())
        results = []
        for action, suffix in (("checkin", "CheckIn"), ("checkout", "CheckOut")):
            name = f"WEB-INF/classes/HTNG/messages/HTNG_Hotel{suffix}NotifRQ.xsd"
            schema = etree.XMLSchema(etree.parse("http://htng.org/2011B", xml_parser))
            wire = CmndHtngAdapter().encode_event({
                "action": action, "room": "00101", "first_name": "Zoë & Test", "last_name": "SYNTHETIC",
                "language": "en-US", "extra": {"hotel_code": "LAB", "guest_id": "synthetic-1",
                "guest_id_type": "1", "telephone_extension": "0101", "housekeeping_status": "VACANT_CLEAN"},
            })
            body = etree.fromstring(wire).find(f"{{{SOAP}}}Body")[0]
            schema.assertValid(body)
            results.append({"action": action, "schema_sha256": hashlib.sha256(archive.read(name)).hexdigest(), "valid": True})
        print(json.dumps({"schema_checks": results, "reference_assembly": "reachable declarations grouped by namespace in memory",
                          "cmnd_runtime_tested": False, "tv_tested": False}, indent=2))


if __name__ == "__main__":
    main()
