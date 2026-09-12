import zipfile

import pytest

from innaware_pms_emulator.cmnd_reference import inspect_reference

WEB = b'''<web-app xmlns="http://java.sun.com/xml/ns/javaee">
<servlet><servlet-name>cxf</servlet-name><servlet-class>org.apache.cxf.transport.servlet.CXFServlet</servlet-class></servlet>
<servlet-mapping><servlet-name>cxf</servlet-name><url-pattern>/services/*</url-pattern></servlet-mapping>
</web-app>'''
SECURITY = b'''<beans xmlns="http://www.springframework.org/schema/beans" xmlns:j="http://cxf.apache.org/jaxws" xmlns:s="http://www.springframework.org/schema/security">
<j:endpoint id="stayNotification" address="/StayNotification"/>
<s:http><s:intercept-url pattern="/services/**" access="permitAll"/></s:http>
<bean id="private"><property name="password" value="DO_NOT_EXPORT"/></bean>
</beans>'''


def archive(tmp_path, web=WEB, security=SECURITY):
    path = tmp_path / "synthetic.war"
    with zipfile.ZipFile(path, "w") as output:
        output.writestr("WEB-INF/web.xml", web)
        output.writestr("WEB-INF/spring-security.xml", security)
    return path


def test_reference_inspection_exports_only_routing_metadata(tmp_path):
    path = archive(tmp_path)
    before = path.read_bytes()
    result = inspect_reference(path)
    assert result["candidate_service_path"] == "/SmartInstall/services/StayNotification"
    assert result["servlet_access_rule"] == "permitAll"
    assert not result["authentication_verified"] and not result["cmnd_runtime_tested"]
    assert "DO_NOT_EXPORT" not in repr(result)
    assert path.read_bytes() == before
    assert inspect_reference(path, context_path="/Lab")["candidate_service_path"] == "/Lab/services/StayNotification"


@pytest.mark.parametrize("context", ["../secret", "/../secret", "/a?x=1", "/a%2fb", "/a\\b"])
def test_reference_rejects_invalid_context_before_opening(context):
    with pytest.raises(ValueError, match="Context path"):
        inspect_reference("not-opened.war", context_path=context)


@pytest.mark.parametrize("security", [b"<empty/>", SECURITY.replace(b"/StayNotification", b"https://example.invalid/"),
                                     b"<!DOCTYPE a><a/>", b"x" * 65537],
                         ids=["missing", "absolute", "doctype", "oversize"])
def test_reference_fails_closed_on_invalid_declarations(tmp_path, security):
    with pytest.raises(ValueError):
        inspect_reference(archive(tmp_path, security=security))
