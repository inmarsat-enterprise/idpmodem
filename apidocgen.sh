#!/bin/bash
pdoc --html idpmodem --output-dir docs --force
mv ./docs/idpmodem/* ./docs
rm -r ./docs/idpmodem
