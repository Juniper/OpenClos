#!/bin/bash

# $1 is the dbUrl in format of "sqlite:///<relative_path_to_db_file>"
url=$1
path=${url/sqlite:\/\/\//}
backup="$path.`date +%Y%m%d-%H%M%S`"
echo "copying '$path' to '$backup'"
cp "$path" "$backup"
