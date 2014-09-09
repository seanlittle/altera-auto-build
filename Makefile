ifeq ($(OS),Windows_NT)
# initialize paths to windows tools
MSIM_PATH = /cygdrive/c/modelsim_dlx_10.3/win32pe
QUARTUS_PATH = /cygdrive/c/altera/14.0/quartus/bin64
IP_GEN_PATH = /cygdrive/c/altera/14.0/quartus/sopc_builder/bin
ROOT = ..

TOOL_ROOT := $(subst /cygdrive/c,c:,$(ROOT))
TOOL_MSIM := $(subst /cygdrive/c,c:,$(MSIM_PATH))
PY = python3
else
# initialize paths to linux tools
MSIM_PATH = /tools/modelsim/modelsim_10.3/modelsim_dlx/bin
QUARTUS_PATH = /tools/altera/quartus_14.0/quartus/bin
IP_GEN_PATH = /tools/altera/quartus_14.0/quartus/sopc_builder/bin
ROOT = ..

TOOL_ROOT = $(ROOT)
TOOL_MSIM = $(MSIM_PATH)
PY = python3.3
endif

export PATH := $(MSIM_PATH):$(QUARTUS_PATH):$(IP_GEN_PATH):$(PATH)

# general settings
BLD_DIR = bld
MODULES_DIR = $(BLD_DIR)/modules
FILES = files
FILES2 = 

UTILS = utils.py
DEPS = dependencies.mk
CMD = touch
SYN_DEPS = $(BLD_DIR)/syn_deps

QSH = quartus_sh
IPG = ip-generate
ALTERA_SIM_LIBS = $(TOOL_ROOT)/altera_libs

# entry points
TOP = fpga3_top
TOP_TB = fpga3_top
#TOP = cec_decr
#TOP_TB = cec_decr_tb
#TOP = cec
#TOP_TB = cec_tb
#TOP = sram_top
#TOP_TB = qdr_controller_tb

# simulation settings
VLOG = vlog
VLOG_OPTIONS = 
VSIM = vsim
LIBS = 
VSIM_OPTIONS = -i $(LIBS)
WORK = work
ELAB_LIBS_FILE =  $(BLD_DIR)/elab_libs
INI = ./modelsim.ini

# synthesis settings
SYNTH_MAKE = synth.mk
SYN_DIR = $(BLD_DIR)/$(TOP)
PROJECT = $(SYN_DIR)/$(TOP)
ASSIGNMENT_FILES = $(SYN_DIR)/$(PROJECT).qpf $(SYN_DIR)/$(PROJECT).qsf
FAMILY = "Arria 10"
DEVICE = 10AX115S3F45I2SGES
BOARDFILE = example_pins.qsf
WARNING_FILE = $(SYN_DIR)/synth_warnings.txt
PREVIOUS_WARNINGS = $(SYN_DIR)/synth_warnings_prev.txt
CPUS = 8

# search variable
S = 

export

default:
#	@echo $(VSIM_OPTIONS)
#	which $(VLOG)
#	@echo $(OS)
	@echo $(PATH)

search:
	$(PY) $(UTILS) search $(FILES) $(ROOT) $(S)

emacs_auto:
	$(PY) $(UTILS) emacs_auto $(FILES) $(ROOT)

deps: $(DEPS)

env: $(INI) $(MODULES_DIR)

#comp: env $(BLD_DIR)/qdr_controller_t
comp: env $(DEPS)
	make --no-print-directory -f $(DEPS) $(MODULES_DIR)/$(TOP_TB)

opt:
	@echo "Not yet supported"

sim: comp
	$(eval VSIM_OPTIONS += $(shell cat $(ELAB_LIBS_FILE)))
	$(VSIM) $(VSIM_OPTIONS) work.$(TOP_TB)&
	@echo "quit -sim; $(VSIM) $(VSIM_OPTIONS) work.$(TOP_TB);" > rerun.do

synth: env $(DEPS) $(SYN_DIR)
# want to force a modelsim recompile for two reasons:
# 1) need to find only the files that are dependent on the top level file (no testbench stuff); using a trick
#    in the dependencies.mk to help with that, so we need to run that make from a clean slate
# 2) it is a healthy thing to verify that modelsim can compile the files before passing them to quartus;
#    coding errors are easier to diagnose and solve outside the synthesis tool
	@rm -rf $(MODULES_DIR)/* $(SYN_DEPS) $(PROJECT).qsf
	make --no-print-directory -f $(DEPS) $(MODULES_DIR)/$(TOP)
	$(PY) $(UTILS) synth_tcl_file $(SYN_DEPS) $(SYN_DIR) $(TOP) $(BOARDFILE) $(FAMILY) $(DEVICE)
	make --no-print-directory -f $(SYNTH_MAKE) clean
	make --no-print-directory -f $(SYNTH_MAKE) all

quartus:
	quartus $(PROJECT).qpf&

altera_libs: $(INI)

warnings:
	@make --no-print-directory -f $(SYNTH_MAKE) $(WARNING_FILE)
	@printf "\n\nBuild warnings:\n"
	@cat $(WARNING_FILE)

diff_warnings:
	@make --no-print-directory -f $(SYNTH_MAKE) diff

diff_files:
# requires that user pass in FILES2 from the command line
	$(PY) $(UTILS) diff_files $(FILES) $(FILES2) $(ROOT)

clean:
	rm -f $(DEPS)
	rm -rf $(MODULES_DIR)
	rm -f $(INI)
	find $(BLD_DIR) -type f -name "*.mk" -exec rm -f {} \;

nuke:
# normally don't want to clean such that the libraries need to be rebuilt
	rm -rf $(ALTERA_SIM_LIBS)
	rm -rf $(WORK)
	rm -rf $(BLD_DIR)

$(INI): $(BLD_DIR)/altera_libs
# all operations that modify the modelsim.ini file should be put here
	@mkdir -p $(BLD_DIR)
	vlib $(WORK)
	vmap altera_mf_ver $(ALTERA_SIM_LIBS)/verilog_libs/altera_mf_ver
	vmap altera_lnsim_ver $(ALTERA_SIM_LIBS)/verilog_libs/altera_lnsim_ver
	vmap altera_ver $(ALTERA_SIM_LIBS)/verilog_libs/altera_ver
	vmap lpm_ver $(ALTERA_SIM_LIBS)/verilog_libs/lpm_ver
	vmap sgate_ver $(ALTERA_SIM_LIBS)/verilog_libs/sgate_ver
	vmap arriav_hssi_ver $(ALTERA_SIM_LIBS)/verilog_libs/arriav_hssi_ver
	vmap arriav_pcie_hip_ver $(ALTERA_SIM_LIBS)/verilog_libs/arriav_pcie_hip_ver
	vmap arriav_ver $(ALTERA_SIM_LIBS)/verilog_libs/arriav_ver
	vmap cyclonev_hssi_ver $(ALTERA_SIM_LIBS)/verilog_libs/cyclonev_hssi_ver
	vmap cyclonev_pcie_hip_ver $(ALTERA_SIM_LIBS)/verilog_libs/cyclonev_pcie_hip_ver
	vmap cyclonev_ver $(ALTERA_SIM_LIBS)/verilog_libs/cyclonev_ver
	vmap stratixv_hssi_ver $(ALTERA_SIM_LIBS)/verilog_libs/stratixv_hssi_ver
	vmap stratixv_pcie_hip_ver $(ALTERA_SIM_LIBS)/verilog_libs/stratixv_pcie_hip_ver
	vmap stratixv_ver $(ALTERA_SIM_LIBS)/verilog_libs/stratixv_ver
	vmap twentynm_hip_ver $(ALTERA_SIM_LIBS)/verilog_libs/twentynm_hip_ver
	vmap twentynm_hssi_ver $(ALTERA_SIM_LIBS)/verilog_libs/twentynm_hssi_ver
	vmap twentynm_ver $(ALTERA_SIM_LIBS)/verilog_libs/twentynm_ver

$(BLD_DIR):
	mkdir $(BLD_DIR)

$(MODULES_DIR):
	mkdir $(MODULES_DIR)

$(SYN_DIR):
	mkdir $(SYN_DIR)

$(DEPS): $(UTILS) $(FILES) globals.py
	rm -rf $(SYN_DEPS)
	$(PY) $(UTILS) deps $(FILES) $(MODULES_DIR) $(DEPS) $(ROOT) $(SYN_DEPS) $(ELAB_LIBS_FILE)

$(BLD_DIR)/altera_libs:
	$(QSH) --simlib_comp -tool modelsim -language verilog -tool_path $(TOOL_MSIM) -directory $(ALTERA_SIM_LIBS) -rtl_only
	$(QSH) --simlib_comp -tool modelsim -language verilog -family arriav -tool_path $(TOOL_MSIM) -directory $(ALTERA_SIM_LIBS) -no_rtl
	$(QSH) --simlib_comp -tool modelsim -language verilog -family cyclonev -tool_path $(TOOL_MSIM) -directory $(ALTERA_SIM_LIBS) -no_rtl
	$(QSH) --simlib_comp -tool modelsim -language verilog -family stratixv -tool_path $(TOOL_MSIM) -directory $(ALTERA_SIM_LIBS) -no_rtl
	$(QSH) --simlib_comp -tool modelsim -language verilog -family arria10 -tool_path $(TOOL_MSIM) -directory $(ALTERA_SIM_LIBS) -no_rtl
	@touch $(BLD_DIR)/altera_libs
