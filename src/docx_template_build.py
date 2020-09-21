#! /usr/bin/env python3

'''
Creates C code for creating .docx files using internal template .docx content.

Args:

    -i <docx-path>
        Set template .docx file to extract from.

    -o <out-path>
        Set name of output files.
        
        We write to <out-path>.c and <out-path>.h.
'''

import io
import os
import sys
import textwrap


def system(command):
    '''
    Like os.system() but raises exception if command fails.
    '''
    e = os.system(command)
    if e:
        print(f'command failed: {command}')
        assert 0

def read(path):
    '''
    Returns contents of file.
    '''
    with open(path) as f:
        return f.read()

def write(text, path):
    '''
    Writes text to file.
    '''
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)

def write_if_diff(text, path):
    try:
        old = read(path)
    except Exception:
        old = None
    if text != old:
        write(text, path)

def check_path_safe(path):
    '''
    Raises exception unless path consists only of characters and sequences that
    are known to be safe for shell commands.
    '''
    if '..' in path:
        raise Exception(f'Path is unsafe because contains "..": {path!r}')
    for c in path:
        if not c.isalnum() and c not in '/._-':
            #print(f'unsafe character {c} in: {path}') 
            raise Exception(f'Path is unsafe because contains "{c}": {path!r}')

def path_safe(path):
    '''
    Returns True if path is safe else False.
    '''
    try:
        check_path_safe(path)
    except Exception:
        return False
    else:
        return True

assert not path_safe('foo;rm -rf *')
assert not path_safe('..')
assert path_safe('foo/bar.x')


def main():
    path_in = None
    path_out = None
    args = iter(sys.argv[1:])
    while 1:
        try: arg = next(args)
        except StopIteration: break
        if arg == '-h' or arg == '--help':
            print(__doc__)
            return
        elif arg == '-i':
            path_in = next(args)
        elif arg == '-o':
            path_out = next(args)
        else:
            assert 0
    
    if not path_in:
        raise Exception('Need to specify -i <docx-path>')
    if not path_in:
        raise Exception('Need to specify -o <out-path>')
    
    check_path_safe(path_in)
    check_path_safe(path_out)
    path_temp = f'{path_in}.dir'
    os.system(f'rm -r "{path_temp}" 2>/dev/null')
    system(f'unzip -q -d {path_temp} {path_in}')
    
    out_c1 = io.StringIO()
    out_c1.write(f'/* THIS IS AUTO-GENERATED CODE, DO NOT EDIT. */\n')
    out_c1.write(f'\n')
    out_c1.write(f'#include "{os.path.basename(path_out)}.h"\n')
    out_c1.write(f'\n')
    
    out_c2 = io.StringIO()
    
    out_c3 = io.StringIO()
    
    out_c3.write(f'int extract_docx_write(extract_zip_t* zip, const char* word_document_xml, int word_document_xml_length)\n')
    out_c3.write(f'{{\n')
    out_c3.write(f'    int e = -1;\n')
    
    for dirpath, dirnames, filenames in os.walk(path_temp):
        
        if 0:
            # Write code to create directory item in zip. This isn't recognised by zipinfo, and doesn't
            # make Word like the file.
            #
            name = dirpath[ len(path_temp)+1: ]
            if name:
                if not name.endswith('/'):
                    name += '/'
                    out_c3.write(f'        if (extract_zip_write_file(zip, NULL, 0, "{name}")) goto end;\n')
        
        for filename in sorted(filenames):
            #name = filename[len(path_temp)+1:]
            path = os.path.join(dirpath, filename)
            name = path[ len(path_temp)+1: ]
            text = read(os.path.join(dirpath, filename))
            text = text.replace('"', '\\"')
            
            # Need to convert newlines to cr-nl to make output identical to
            # when we use zip/unzip on template .docx file. Have tried to use
            # binary read instead but this requires decoding and with latin-1
            # ends up changing other bytes in the content. I.e. reading file as
            # text not binary seems to be the right thing.
            #
            text = text.replace('\n', '\\r\\n"\n                "')
            text = f'"{text}"'
            
            if name == 'word/document.xml':
                # We make the contents of word/document.xml available as global
                # extract_docx_word_document_xml, and our generated C code
                # substitutes with the <word_document_xml> arg.
                out_c2.write(f'char extract_docx_word_document_xml[] = {text};\n')
                out_c2.write(f'int  extract_docx_word_document_xml_len = sizeof(extract_docx_word_document_xml) - 1;\n')
                out_c2.write(f'\n')
                
                out_c3.write(f'    if (word_document_xml) {{\n')
                out_c3.write(f'        if (extract_zip_write_file(zip, word_document_xml, word_document_xml_length, "{name}")) goto end;\n')
                out_c3.write(f'    }}\n')
                out_c3.write(f'    else {{\n')
            
            else:
                out_c3.write(f'    {{\n')
            
            out_c3.write(f'        char text[] = {text}\n')
            out_c3.write(f'                ;\n')
            out_c3.write(f'        if (extract_zip_write_file(zip, text, sizeof(text)-1, "{name}")) goto end;\n')
            out_c3.write(f'    }}\n')
            out_c3.write(f'    \n')
    
    out_c3.write(f'    e = 0;\n')
    out_c3.write(f'    end:\n')
    out_c3.write(f'    return e;\n')
    out_c3.write(f'}}\n')
    
    out_c = ''
    out_c += out_c1.getvalue()
    out_c += out_c2.getvalue()
    out_c += out_c3.getvalue()
    write_if_diff(out_c, f'{path_out}.c')
    
    out = io.StringIO()
    out.write(f'#ifndef EXTRACT_DOCX_TEMPLATE_H\n')
    out.write(f'#define EXTRACT_DOCX_TEMPLATE_H\n')
    out.write(f'\n')
    out.write(f'/* THIS IS AUTO-GENERATED CODE, DO NOT EDIT. */\n')
    out.write(f'\n')
    out.write(f'#include "zip.h"\n')
    out.write(f'\n')
    out.write(f'extern char extract_docx_word_document_xml[];\n')
    out.write(f'extern int  extract_docx_word_document_xml_length;\n')
    out.write(f'/* Contents of internal .docx template\'s word/document.xml. */\n')
    out.write(f'\n')
    out.write(f'int extract_docx_write(extract_zip_t* zip, const char* word_document_xml, int word_document_xml_length);\n')
    out.write(f'/* Writes internal template .docx items to <zip>, using <word_document_xml>\n')
    out.write(f'instead of the internal template\'s word/document.xml. */\n')
    out.write(f'\n')
    out.write(f'#endif\n')
    write_if_diff(out.getvalue(), f'{path_out}.h')
    os.system(f'rm -r "{path_temp}"')
    
if __name__ == '__main__':
    main()