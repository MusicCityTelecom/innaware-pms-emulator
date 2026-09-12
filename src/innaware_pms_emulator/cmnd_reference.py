"""Read only declarative CMND endpoint metadata; never load vendor code."""
from __future__ import annotations

import hashlib
import re
import zipfile

from .protocols.cmnd import parse_xml


def inspect_reference(archive_path, *, context_path: str = "/SmartInstall") -> dict:
    if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)*", context_path):
        raise ValueError("Context path must contain only slash-separated application names")
    names = ("WEB-INF/web.xml", "WEB-INF/spring-security.xml")
    documents = {}
    hashes = {}
    with zipfile.ZipFile(archive_path) as archive:
        for name in names:
            matches = [item for item in archive.infolist() if item.filename == name]
            if len(matches) != 1 or matches[0].file_size > 65536:
                raise ValueError("Missing, duplicate or oversized CMND deployment descriptor")
            data = archive.read(matches[0])
            documents[name] = parse_xml(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
    web = documents[names[0]]
    ns = "{http://java.sun.com/xml/ns/javaee}"
    cxf_names = {node.findtext(ns + "servlet-name") for node in web.findall(ns + "servlet")
                 if node.findtext(ns + "servlet-class") == "org.apache.cxf.transport.servlet.CXFServlet"}
    mappings = [node.findtext(ns + "url-pattern") for node in web.findall(ns + "servlet-mapping")
                if node.findtext(ns + "servlet-name") in cxf_names]
    security = documents[names[1]]
    addresses = [node.get("address") for node in security.iter("{http://cxf.apache.org/jaxws}endpoint")
                 if node.get("id") == "stayNotification"]
    if len(mappings) != 1 or len(addresses) != 1:
        raise ValueError("Cannot uniquely resolve the CMND StayNotification declaration")
    mapping, address = mappings[0], addresses[0]
    if not mapping or not mapping.endswith("/*") or not address or not re.fullmatch(r"/[A-Za-z0-9_-]+", address):
        raise ValueError("Unsupported CMND endpoint mapping shape")
    prefix = mapping[:-2]
    if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", prefix):
        raise ValueError("Invalid CMND servlet prefix")
    rules = [node for node in security.iter("{http://www.springframework.org/schema/security}intercept-url")
             if node.get("pattern") == prefix + "/**"]
    return {
        "evidence": "deployment-descriptor-observed",
        "context_path": context_path,
        "context_path_source": "operator input; not established by archive descriptors",
        "candidate_service_path": context_path + prefix + address,
        "servlet_access_rule": rules[0].get("access") if len(rules) == 1 else "unknown",
        "authentication_verified": False,
        "cmnd_runtime_tested": False,
        "tv_tested": False,
        "descriptor_sha256": hashes,
    }
