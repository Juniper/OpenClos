Swagger-Render
==============

Creates a single HTML file from a Swagger API. Supports an arbitrary subset
of the 2.0 specification.

usage
-----

::

    swagger-render api.yml -o index.html

You can add the ``--watch`` / ``-w`` flag to watch the Swagger file for changes
and re-render automatically with ``pyinotify``, which needs to be installed
separately from PyPI.

special options
---------------

If you add ``x-swagger-render-group-by-tags: false`` into the info section of
the Swagger file the methods wont be grouped by tags so that there are no
duplicates listed for each tag the method has. Instead the tags are shown in
every method.

license
-------

MIT, see ``LICENSE``
