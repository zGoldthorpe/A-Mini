" Vim syntax for A-Mi
"
" To load syntax manually:
" :source ami.vim
"
" To load syntax automatically:
" - copy ami.vim into folder ~/.vim/syntax/
" - create a file ~/.vim/ftdetect/ami.vim containing the line
"       autocmd BufNewFile,BufRead *.ami setf ami

if exists("b:current_syntax")
    finish
endif

syn keyword amiCommand phi goto branch exit read write

syn match amiOp '[+\-*?:<=\[,\]]'
syn match amiInteger '-\?\d\+'
syn match amiLabel '@[.a-zA-Z0-9_]\+'
syn match amiReg '%[.a-zA-Z0-9_]\+'

syn region amiBrkPt start='^\s*brkpt' end='$'
syn region amiMeta start='#!' start='@!' start='%!' end=':'
syn match amiComment ';.*$' contains=amiMeta

let b:current_syntax = "ami"

" run :h syntax to find the supported colour names

hi def link amiCommand  Statement
hi def link amiOp       Operator
hi def link amiInteger  Constant
hi def link amiReg      Identifier
hi def link amiLabel    Type
hi def link amiComment  Comment
hi def link amiMeta     PreProc
hi def link amiBrkPt    Todo
