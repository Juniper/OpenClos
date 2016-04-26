import sys
import traceback
from datetime import datetime

import yaml
import click
from jinja2 import Environment, PackageLoader

from .colors import colors
from .errors import InvalidReferenceError
from .filters import add_filters
from .__version__ import __version__


def resolve(base, val):
    """
    Makes a normal dictionary from a JSON Schema one
    """

    if type(val) is dict:
        data = {}
        for key, value in val.items():
            if key == "$ref" and type(value) is str:
                f_value = value
                value = value.split("/")
                assert value.pop(0) == "#"
                pos = base
                while len(value) > 0:
                    where_to = value.pop(0)
                    try:
                        pos = pos[where_to]
                    except KeyError:
                        try:
                            pos = pos[int(where_to)]
                        except ValueError:
                            raise InvalidReferenceError(f_value, where_to)
                data.update(resolve(base, resolve(base, pos)))
            if key == "allOf":
                return all_of(base, *value)
            else:
                data[key] = resolve(base, value)
        return data
    if type(val) is list:
        return [resolve(base, item) for item in val]
    else:
        return val


def all_of(root=None, *items):
    """
    Merges the given items recursively

    >>> all_of("3", "2")
    '2'
    >>> sorted(all_of([1, 2], [3, 4]))
    [1, 2, 3, 4]
    >>> from pprint import pprint
    >>> pprint(all_of({"type": "object", "items": [1, 2], "foo": {"a": "bar"}}, \
                      {"type": "object", "items": [3], "foo": {"b": "baz"}}, \
                      {"items": [4]}))
    {'foo': {'a': 'bar', 'b': 'baz'}, 'items': [4, 3, 1, 2], 'type': 'object'}
    """

    items = list(items)

    if type(items[0]) == list:
        data = items.pop()
        while len(items) > 0:
            data += items.pop()
        return resolve(root, data)
    if type(items[0]) in [str, int]:
        return items.pop()

    items = resolve(root, items)
    data = items.pop(0)

    for item in items:
        for key, value in item.items():
            if key in data:
                data[key] = all_of(root, data[key], value)
            else:
                data[key] = value

    return resolve(root, data)


def merge_parameters(params1, params2):
    """
    Merges parameter lists, where uniqueness is defined by a combination of
    its name and location

    >>> from pprint import pprint
    >>> pprint(merge_parameters([{"name": "a", "in": "a"}, \
                                 {"name": "b", "in": "a"}], \
                                [{"name": "a", "in": "a", "data": "c"}, \
                                 {"name": "b", "in": "b"}]))
    [{'data': 'c', 'in': 'a', 'name': 'a'},
     {'in': 'a', 'name': 'b'},
     {'in': 'b', 'name': 'b'}]
    """

    data = {}
    for param in params1 + params2:
        data[param["name"] + "_" + param["in"]] = all_of({}, param)
    return sorted(list(data.values()), key=lambda x: x["name"] + x["in"])


def make_logical(data):
    for methods in data["paths"].values():
        if "parameters" in methods:
            common_params = methods["parameters"]
            for method_name, method in methods.items():
                if method_name == "parameters":
                    continue
                params = method.get("parameters", [])
                method["parameters"] = merge_parameters(common_params, params)


def get_tags(data):
    """
    Gets all of the tags in the data

    >>> get_tags({ \
        "paths": { \
            "1": {"a": {"tags": ["c"]}, \
                  "b": {"tags": ["c"]}}, \
            "2": {"a": {"tags": ["b"]}, \
                  "d": {}}, \
            "3": {"c": {"tags": ["d", "e"]}} \
        } \
    })
    ['', 'b', 'c', 'd', 'e']
    """
    tags = set()
    for methods in data["paths"].values():
        for method in methods.values():
            if type(method) is list:
                continue
            tags |= set(method.get("tags", [""]))

    return sorted(list(tags))


def render(env, yaml_path, out):
    with open(yaml_path, "r") as fp:
        data = yaml.load(fp.read())
    data = resolve(data, data)
    make_logical(data)
    template = env.get_template("page.html")

    if out is not sys.stdout:
        out.truncate(0)

    out.write(template.render(__version__=__version__,
                              __time__=datetime.utcnow(),
                              _colors=colors,
                              _tags=get_tags(data), **data))


def render_watch_notify(env, yaml_path, out):
    print("File changed, rendering")
    try:
        render(env, yaml_path, out)
    except Exception:
        traceback.print_exc()


def render_watch(env, yaml_path, out):
    try:
        import pyinotify
    except ImportError:
        raise click.UsageError(("Cant import pyinotify, "
                                "please install with pip"))
    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm)
    wm.add_watch(yaml_path, pyinotify.IN_CLOSE_WRITE)
    notifier.loop(daemonize=False,
                  callback=lambda _: render_watch_notify(env, yaml_path, out))


@click.command()
@click.argument("swagger_path", type=click.Path(exists=True))
@click.option("--out", "-o", default=sys.stdout, type=click.File("w"),
              help="Where to write the generated HTML")
@click.option("--watch", "-w", is_flag=True)
def main(swagger_path, out, watch):
    env = Environment(loader=PackageLoader("swagger_render"))
    add_filters(env)

    if watch:
        if out is sys.stdout:
            raise click.BadParameter("-o needs to be specified if using -w")
        render_watch(env, swagger_path, out)
    else:
        render(env, swagger_path, out)


if __name__ == "__main__":
    main()
