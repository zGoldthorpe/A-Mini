" Vim syntax for A-Mi
"
"$ source ami.vim

if exists("b:current_syntax")
    finish
endif

syn keyword amiCommand phi goto branch exit read write

syn match amiInteger '-\?\d\+'
syn match amiLabel '@[.a-zA-Z0-9_]\+'
syn match amiReg '%[.a-zA-Z0-9_]\+'

syn region amiMeta start='#!' start='@!' start='%!' end=':'
syn match amiComment ';.*$' contains=amiMeta

let b:current_syntax = "ami"

hi def link amiCommand  Statement
hi def link amiInteger  Constant
hi def link amiReg      Type
hi def link amiLabel    Identifier
hi def link amiComment  Comment
hi def link amiMeta     PreProc
