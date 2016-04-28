import markdown
from jinja2 import evalcontextfilter


@evalcontextfilter
def md(eval_ctx, value):
    return markdown.markdown(value)


@evalcontextfilter
def sane(eval_ctx, value):
    return ("_".join(value)).replace("/", "_").replace("{", "_").replace("}",
                                                                         "_")


@evalcontextfilter
def filter(eval_ctx, value):
    paths = value[0]
    tag = value[1]
    care_about_tag = value[2]

    for path_name, methods in sorted(paths.items()):
        for method_name, method in sorted(methods.items()):
            if method_name == "parameters":
                continue
            if not care_about_tag:
                yield path_name, method_name, method
            else:
                if tag == "" and len(method.get("tags", [])) == 0:
                    yield path_name, method_name, method
                elif len(tag) > 0 and tag in method.get("tags", []):
                    yield path_name, method_name, method


@evalcontextfilter
def schema(eval_ctx, value):
    if "schema" in value:
        return value["schema"]
    if "type" in value:
        if value["type"] is "list":
            if "items" in value:
                return [schema(eval_ctx, value["items"])]
            return []
        ret = ""
        if "format" in value:
            ret += value["format"] + " "
        ret += value["type"]
        return ret
    return None


@evalcontextfilter
def render_object(eval_ctx, obj, offset=0):
    if obj is None:
        return ""
    if type(obj) is str:
        return obj

    if "type" in obj and obj["type"] == "array":
        objecty = (obj["items"].get("type", "object") == "object"
                   or "properties" in obj["items"])
        if "items" in obj and objecty:
            return "<div class=\"schema\">[{}]</div>".format(
                render_object(eval_ctx, obj["items"], offset + 1))
        return ""

    required = obj.get("required", [])
    properties = obj.get("properties", {})
    out = ""
    for key, value in sorted(properties.items()):
        out += "<div class=\"schema\">"
        out += "<span class=\"sKey\">{}</span>".format(key)
        out += " ("

        itype = value.get("type", None)
        if not itype and "properties" in value:
            itype = "object"

        if itype:
            out += "<span class=\"sType\">"
            if "format" in value:
                out += "{} ".format(value["format"])
            out += itype

            if itype == "array" and "items" in value:
                out += "[{}]".format(value["items"].get("type", "object"))

        out += "</span>"

        if key not in required:
            out += ", <span class=\"sOptional\">optional</span>"

        out += ")"

        if "description" in value:
            out += ": <span class=\"sDescription\">{}</span>".format(
                markdown.markdown(value["description"]))

        if itype == "object" or "items" in value:
            out += render_object(eval_ctx, value, offset + 1)

        if "enum" in value:
            out += "<span class=\"enum\">[{}]</span>".format(
                " | ".join(value["enum"]))

        out += "</div>"

    return out


def add_filters(env):
    env.filters["md"] = md
    env.filters["sane"] = sane
    env.filters["schema"] = schema
    env.filters["render"] = render_object
    env.filters["filter"] = filter
