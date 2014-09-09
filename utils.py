import re
import csv
import os
import platform
import difflib

import globals


# process altera generated TCL file and extract the libraries for the -L switches
def ext(file):
    fid = open(file, 'r')
    p = re.compile('\-work\s+(\w+)')
    s = set(p.findall(fid.read()))
    fid.close()
    return s


# use CSV file to generate QSF file that defines pin locations and IO-standard
def gen_pin_script(csv_in, qsf_out):
    fid = open(csv_in, 'r')
    out = open(qsf_out, 'w')
    csv_fid = csv.reader(fid, delimiter=',')
    skip = 1
    for row in csv_fid:
        if (skip == 1):
            skip = 0
            continue
        if row[2] == 'virtual':
            pin_str = 'VIRTUAL_PIN'
        else:
            pin_str = 'PIN_{0}'.format(row[2])
        print('set_location_assignment {0} -to {1}'.format(pin_str, row[1]), file=out)
        print('set_instance_assignment -name IO_STANDARD "{0}" -to {1}'.format(row[3], row[1]), file=out)
    fid.close()
    out.close()
    print('Successfully wrote {0}\n'.format(qsf_out))

# scripts that generate the dependencies
blackbox_str = 'SIM_BLACKBOX'

# note that ONLY one space is allowed between the 'REQUIRE' string and the directive
ip_str = 'REQUIRE IP\d+'
qsys_str = 'REQUIRE [\w\.\d]+'

elab_cmd = ''# populated in the gen_rule method

tcl_ip_indx = 0

auto_bb_table = globals.get_auto_bb_table()


def remove_comments(txt, start_blk, end_blk):
#    global blackbox_str
    p = re.compile('{0}.*?{1}'.format(re.escape(start_blk), re.escape(end_blk)), re.MULTILINE|re.DOTALL)
    if end_blk != '\n':
        txt = p.sub('', txt)
    else:
        # need to preserve the compile directive comments by changing the comment character to something else (// to ## in this case)
        directive_str = '(({0}))'.format(')|('.join({blackbox_str, ip_str, qsys_str}))
        p2 = re.compile(re.escape(start_blk) + '\s*#' + directive_str)
        txt = p2.sub(r'## #\1', txt)
        txt = p.sub('\n', txt)
    return txt


def gen_verilog_rule(file, modules_dir, insub):
    # does not support systemverilog; to support systemverilog/VHDL, we will need to create a separate rule subroutine

    global elab_cmd
    ignore = {'module', 'task', 'begin'}

    fid = open(file, 'r')
    txt = fid.read()
    txt = remove_comments(txt, '/*', '*/')
    txt = remove_comments(txt, '//', '\n')
    fid.close()

    # detect and extract module instances (the following regex is pretty good, but it 
    # is sensitive to bad placement of the ';' character in the port mapping. mis-placing
    # that character will cause an assertion, and the resulting dependency makefile will
    # be only half built. this will lead to further confusing errors for the user)
    p = re.compile('(?:##\s*#([\w\d\. ]+)\s+)?^\s*(\w+)\s+(\w+)\s*\([^;]*\)\s*;', re.MULTILINE|re.DOTALL)
    modules = p.findall(txt)
    # Assuming that the first match is the module declaration
    assert len(modules) > 0 and modules[0][1] == 'module', 'Unexpected module declaration in {0}'.format(file)

    # construct TCL/QSYS IP dependencies; must be done before dependency processing in order to enforce assumption that
    # the QSYS declaration must precede the source declaration in the "files" file
    qsys_makefiles = set()
    if modules[0][0]:
        p = re.compile('##\s*#[A-Z]+ (IP\d+|[\w\.]+)\s+', re.MULTILINE)
        ip_directive_matches = p.findall(txt)
        assert len(ip_directive_matches) > 0, 'Invalid IP directive detected in {0}'.format(file)
        ip_dep = ''
        for m in ip_directive_matches:
            if m[0:2] == 'IP' and m[2].isdigit():
                ip_indx = int(m[2:])
                assert ip_indx <= tcl_ip_indx, 'Invalid IP directive index detected in {0}'.format(file)
                ip_dep = '{0} {1}/../ip{2}'.format(ip_dep, modules_dir, ip_indx)
            else:
                assert not insub, 'Nested QSYS directives are not supported'
                fn = m.replace('.qsys', '')
                assert fn in auto_bb_table, '{0}.qsys must be positioned in the "files" file before {1}'.format(fn, file)
                target_pth = '{0}/../{1}'.format(modules_dir, fn)
                mk = '{0}/{1}.mk'.format(target_pth, fn)
                qsys_makefiles.add(mk)
                ip_dep = '{0} {1}'.format(ip_dep, mk)
        ip_dep = ip_dep + ' '
    else:
        ip_dep = ''

    # don't do dependency analysis if we are in a QSYS sub-makefile
    d = set()
    if not insub:
        first = True
        for m in modules:
            if first:
                first = False
                continue
            # Assuming there is only one module declaration per file
            assert m[1] != 'module', 'Multiple module declarations in {0}'.format(file)
            if not (m[1] in ignore) and m[0] != blackbox_str:
                if not (m[1] in auto_bb_table):
                    d.add(modules_dir + '/' + m[1])
                elif auto_bb_table[m[1]] != '~' and not (auto_bb_table[m[1]] in elab_cmd):
                    elab_cmd = '{0} -L {1}'.format(elab_cmd, auto_bb_table[m[1]])

    # process includes
    p = re.compile('`include\s+([\w\/\.]+)', re.MULTILINE|re.DOTALL)
    includes = p.findall(txt)
    d.union(set(includes))

    # construct make rule
    if len(d) == 0:
        rule = '{0}/{1}: {2} {3}\n'.format(modules_dir, modules[0][2], file, ip_dep)
    else:
        rule = '{0}/{1}: {2} {3}\\\n{4}\n'.format(modules_dir, modules[0][2], file, ip_dep, ' \\\n'.join(d))
    # add qsys makefile calls
    for m in qsys_makefiles:
        rule = '{0}\tmake -f {1} all\n'.format(rule, m)

    rule = '{0}\t$(VLOG) $(VLOG_OPTIONS) -work $(WORK) {1}\n'.format(rule, file)
    rule = '{0}\t@$(CMD) {1}/{2}\n'.format(rule, modules_dir, modules[0][2])
    return True, rule


def gen_tcl_ip_rule(file, modules_dir):
    global elab_cmd, tcl_ip_indx
    precompiled_libraries = globals.get_precompiled_libraries()
    libs = ext(file)
    pth = os.path.dirname(os.path.abspath(file))
    fn = os.path.basename(file)
    if 'CYGWIN' in platform.system():
        pth = pth.replace('/cygdrive/c', 'c:')
    for l in libs:
        if not (l in elab_cmd):
            if l in precompiled_libraries:
                elab_cmd = '{0} -L {1}'.format(elab_cmd, l)
            else:
                cmd = pth + '/libraries/' + l
                elab_cmd = '{0} -L {1}'.format(elab_cmd, cmd)

    target_file = '{0}/../ip{1}'.format(modules_dir, tcl_ip_indx)
    rule = '{0}: {1}\n'.format(target_file, file)
    rule = '{0}\t$(VSIM) -c -do "cd {1}; source {2}; com; quit -f"\n'.format(rule, pth, fn)
#    rule = '{0}\t$(VSIM) -c -do "source {1}; com; quit -f"\n'.format(rule, file) #dev_com
    rule = '{0}\t@touch {1}\n'.format(rule, target_file)
    tcl_ip_indx += 1
    return False, rule


def gen_qsys_rule(file, modules_dir, syn_deps_file):
    # assumptions:
    # 1) There are no QSYS files with the same filename
    # 2) QSYS declarations in the "files" file are positioned before the source (verilog) files that use them (note that
    #    this is enforced in the code)
    # 3) Top level generated module has the same name as the QSYS file (without the extension)
    # 4) The SPD file is an XML file that contains all the simulation files in the correct compilation order
    # 5) All the generated files have the same module name as the filename
    global auto_bb_table, elab_cmd

    from xml.dom import minidom
    xmldoc = minidom.parse(file)
    mod_tag = xmldoc.getElementsByTagName('module')
    assert len(mod_tag) == 1, 'Did not find the "module" tag in {0}'.format(file)
    assert 'kind' in mod_tag[0].attributes, 'Did not find the "kind" attribute in the first "module" tag in {0}'.format(file)

    pth = os.path.dirname(os.path.abspath(file))
    fn = os.path.basename(file).replace('.qsys', '')
    target_pth = '{0}/../{1}'.format(modules_dir, fn)

    rule = '{0}/{1}.mk: {2}\n'.format(target_pth, fn, file)
    kind = mod_tag[0].attributes['kind'].value
    if kind == 'fifo' or kind == 'lpm_counter' or kind == 'altera_iopll':
        # add appropriate entries to the elab_cmd for simulation
        lib = auto_bb_table['scfifo'] if kind == 'fifo' else auto_bb_table[kind]
        if not (lib in elab_cmd):
            elab_cmd = '{0} -L {1}'.format(elab_cmd, lib)

        # generate the simulation, synthesis and QIP files directly from the ip-generate command
        rule = '{0}\t$(IPG) --project-directory={1} --output-directory={2} --file-set=SIM_VERILOG --report-file=spd:{2}/{3}.spd --system-info=DEVICE_FAMILY=$(FAMILY) --system-info=DEVICE=$(DEVICE) --component-file={4} --generator=extensible\n'.format(rule, pth, target_pth, fn, file)
        rule = '{0}\t$(IPG) --project-directory={1} --output-directory={2} --file-set=QUARTUS_SYNTH --report-file=sopcinfo:{2}/{3}.sopcinfo --report-file=qip:{2}/{3}.qip --system-info=DEVICE_FAMILY=$(FAMILY) --system-info=DEVICE=$(DEVICE) --component-file={4} --generator=extensible --language=VERILOG\n'.format(rule, pth, target_pth, fn, file)

    rule = '{0}\t$(PY) $(UTILS) qsys_mk {1}/{2}.spd {3} {4} $(MODULES_DIR) {1}/{2}.mk\n'.format(rule, target_pth, fn, pth, syn_deps_file)


    # this will globally blackbox all the modules that have the same name as the qsys name
    auto_bb_table[fn] = '~'

    # returning False here because I do not want the dep subroutine to append the QSYS file to the synth_deps file; that
    # is done in the rule that pertains to the file that has the "require" directive
    return False, rule


def gen_rule(file, modules_dir, syn_deps_file, insub=False):
    if os.path.isfile(file):
        e = os.path.splitext(file)[1]
        # support for Verilog files
        if e == '.v' or e == '.vh' or e == '.vo':
            return gen_verilog_rule(file, modules_dir, insub)
        elif e == '.tcl':
            return gen_tcl_ip_rule(file, modules_dir)
        elif e == '.qsys':
            return gen_qsys_rule(file, modules_dir, syn_deps_file)
        else:
            print('files of type {0} are not yet supported'.format(e))
            return False, ''
    else:
        print('file {0} does not exist'.format(file))
        return False, ''


def read_files(files, root):
    root_str = '$(ROOT)'
    inp = open(files, 'r')
    if 'CYGWIN' in platform.system():
        root_top = root.replace('/cygdrive/c', 'c\\:')
    else:
        root_top = root
    txt = remove_comments(inp.read(), '#', '\n').split('\n')
    inp.close()
    return txt, root_str, root_top


def deps(files, modules_dir, makefile, root, syn_deps_file):
    txt, root_str, root_top = read_files(files, root)
    if modules_dir[-1] == '/':
        modules_dir = modules_dir[:-2]
    output = open(makefile, 'w')
    print('{0} = {1}\n'.format('ROOT', root_top), file=output)
    for line in txt:
        line = line.rstrip()
        if not line:
            continue
        elif line[0] == '+' or line[0] == '-':
            print('VLOG_OPTIONS += "{0}"\n'.format(line.replace(root_str, root_top.replace('\\', ''))), file=output)
            continue

        for_synth, r = gen_rule(line.replace(root_str, root), modules_dir, syn_deps_file)
        if root:
            r = r.replace(root, root_str)

        # need to collect all the dependencies from an arbitrary entry point for use in the
        if for_synth:
            r = '{0}\t@echo {1} >> {2}\n'.format(r, line, syn_deps_file)

        # print rule to dependencies makefile
        print(r, file=output)

    output.close()
    print('Wrote {0} successfully\n'.format(makefile))


def write_qsys_makefile(spd_file, qsys_dir, syn_deps_file, modules_dir, output_make):
    spd_file = os.path.abspath(spd_file)
    pth = os.path.dirname(spd_file)
    iscygwin = 'CYGWIN' in platform.system()
    if os.path.isfile(spd_file):
        out = open(output_make, 'w')
        from xml.dom import minidom
        spd = minidom.parse(spd_file)
        files = spd.getElementsByTagName('file')
        assert len(files) > 0, 'Did not find a "file" tag in {0}'.format(spd_file)
        # use a list not a set; want to preserve order
        d = list()
        for f in files:
            assert 'path' in f.attributes, 'Encountered a "file" tag that did not contain a "path" attribute in {0}'.format(spd_file)
            verilog_file = pth + '/' + f.attributes['path'].value
            # can potentially support multiple types of generated files
            fs, rule = gen_rule(verilog_file, modules_dir, syn_deps_file, True)
            if iscygwin:
                rule = rule.replace('/cygdrive/c', 'c\\:')
            print(rule, file=out)
            d.append('{0}/{1}'.format(modules_dir, os.path.splitext(os.path.basename(f.attributes['path'].value))[0]))
#        tl = spd.getElementsByTagName('topLevel')
#        assert len(tl) == 1, 'Did not find the "topLevel" tag in {0}'.format(spd_file)
#        assert 'name' in tl[0].attributes, '"topLevel" tag does not contain a "name" attribute in {0}'.format(spd_file)
        rule = 'all: \\\n{0}\n'.format(' \\\n'.join(d))
        ip_file = spd_file.replace('.spd', '.qip')
    else:
        # need to create the directory because the 'ip-generate' command has not been run
        from subprocess import call
        err = call(['mkdir', '-p', pth])
        out = open(output_make, 'w')

        rule = 'all:\n'
        ip_file = qsys_dir + '/' + os.path.basename(spd_file.replace('.spd', '.qsys'))

    if iscygwin:
        ip_file = ip_file.replace('/cygdrive/c', 'c\\:')
    rule = '{0}\t@echo {1} >> {2}'.format(rule, ip_file, syn_deps_file)
    print(rule, file=out)
    out.close()
    print('Wrote {0} successfully\n'.format(output_make))


# create tab delimited output for easy viewing in Excel and ability to diff
def extract_warnings(report_file, out_id):
    inp = open(report_file, 'rb')
    p = re.compile('(Critical\s+)*Warning\s+\((\d+)\):\s+([^\n\r]+)\r?\n', re.MULTILINE)
    warns = p.findall(inp.read().decode("utf-8", "ignore"))
    for w in warns:
        print('{0}\t{1}\t{2}\t{3}'.format(report_file, w[0], w[1], w[2]), file=out_id)
    inp.close()
    return len(warns)


def write_emacs_autofile(files, root):
    txt, root_str, root_top = read_files(files, root)
    s = set()
    for l in txt:
        if not l or ('+' in l):
            continue
        s.add(os.path.dirname(os.path.abspath(l.replace(root_str, root))))
    #print(*s, sep='\n')
    autofile = 'input.vc'
    out = open(autofile, 'w')
    for f in s:
        print('-y {0}/'.format(f), file=out)
    out.close()
    print('Wrote {0} successfully\n'.format(autofile))
    print('// Local Variables:\n// verilog-library-flags:("-f {0}/{1}")\n// End:'.format(os.getcwd(),autofile))


def search_files(files, root, search_str):
    txt, root_str, root_top = read_files(files, root)
    from subprocess import call
    for l in txt:
        if not l or ('+' in l):
            continue
#        print('grep -HEn {0} {1}'.format(search_str, l.replace(root_str, root)))
        err = call(['grep', '-HEn', format(search_str), l.replace(root_str, root).rstrip()])


def diff_files(files1, files2, root):
    f1, root_str, root_top = read_files(files1, root)
    f2, root_str, root_top = read_files(files2, root)

    l1 = list()
    lf1 = list()
    for f in f1:
        if not f or ('+' in f):
            continue
        l1.append(os.path.basename(f))
        lf1.append(f)
    indx1 = dict((j,i) for i,j in enumerate(l1))

    l2 = list()
    lf2 = list()
    for f in f2:
        if not f or ('+' in f):
            continue
        l2.append(os.path.basename(f))
        lf2.append(f)
    indx2 = dict((j,i) for i,j in enumerate(l2))

    files = set(l1).intersection(set(l2))
    for f in files:
        file1 = lf1[indx1[f]].replace(root_str, root)
        file2 = lf2[indx2[f]].replace(root_str, root)
        if not os.path.isfile(file1):
            print('{0} in {1} does not exist'.format(file1, files1))
            continue
        if not os.path.isfile(file2):
            print('{0} in {1} does not exist'.format(file2, files2))
            continue
        fid = open(file1, 'r')
        txt1 = fid.read().strip().splitlines()
        fid.close()

        fid = open(file2, 'r')
        txt2 = fid.read().strip().splitlines()
        fid.close()
        df = list(difflib.unified_diff(txt1, txt2, fromfile=file1, tofile=file2, lineterm='', n=0))
        if len(df) == 0:
            print('{0} and\n{1} are identical'.format(file1, file2))
        for line in df:
            print(line)
        print('\n')

def write_synth_tcl(synth_deps, bld_dir, top, assignment_file, family, device):
    tcl = bld_dir + '/' + top + '.tcl'
    with open(synth_deps, 'r') as inp:
        srcs = inp.read().splitlines()
        with open(tcl, 'w') as out:
            print('project_new {0}/{1} -overwrite'.format(bld_dir, top), file=out)
            print('set_global_assignment -name TOP_LEVEL_ENTITY {0}'.format(top), file=out)
            with open(assignment_file, 'r') as inp2:
                assignments = inp2.read()
                print(assignments, file=out)
            for s in srcs:
                if '.qip' in s:
                    print('set_global_assignment -name QIP_FILE {0}'.format(s), file=out)
                elif '.qsys' in s:
                    print('set_global_assignment -name QSYS_FILE {0}'.format(s), file=out)
                else:
                    print('set_global_assignment -name SOURCE_FILE {0}'.format(s), file=out)
            print('set_global_assignment -name FAMILY "{0}"'.format(family), file=out)
            print('set_global_assignment -name DEVICE {0}'.format(device), file=out)
            print('project_close', file=out)
    print('Wrote {0} successfully\n'.format(tcl))


# main entry point

if __name__ == "__main__":
    import sys
    if sys.argv[1] == "ext":
        # input: QSYS generated simulation TCL script
        print(*ext(sys.argv[2]), sep='\n')
    elif sys.argv[1] == "gen_pin_script":
        # inputs: CSV file containing pin definitions and IO standard information; output QSF file
        gen_pin_script(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "deps":
        # inputs: files; modules_dir; makefile name; root string; synthesis dependency file
        root = os.path.abspath(sys.argv[5])
        try:
            deps(sys.argv[2], sys.argv[3], sys.argv[4], root, sys.argv[6])
        except AssertionError as e:
            os.remove(sys.argv[4])
            raise AssertionError(e.args)
        # write out elaboration library requirements
        out_id = open(sys.argv[7], 'w')
        print(elab_cmd, file=out_id)
        out_id.close()
    elif sys.argv[1] == "qsys_mk":
        # meant to be called by the makefile, and not directly from the commandline
        # inputs: spd file; qsys path, synthesis dependency file, modules_dir, output makefile name
        write_qsys_makefile(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
    elif sys.argv[1] == "warnings":
        # inputs: space delimited list of report files; warning output file
        out_id = open(sys.argv[3], 'w')
        print('Report\tCritical?\tID\tMessage', file=out_id)
        reports = sys.argv[2].split(' ')
        num = 0
        for r in reports:
            num += extract_warnings(r, out_id)
        out_id.close()
        print('Encountered {0} warnings\n'.format(num))
    elif sys.argv[1] == 'emacs_auto':
        # inputs: files file; root string
        write_emacs_autofile(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'search':
        #inputs: files; root string; search pattern (extended regex)
        search_files(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'diff_files':
        #inputs: files1, files2, root string
        diff_files(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'synth_tcl_file':
        #inputs: synthesis dependency file; project directory; top module name; assignment file; fpga family; device
        write_synth_tcl(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7])
