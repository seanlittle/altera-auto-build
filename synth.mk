# Makefile derived from
# https://github.com/mfischer/Altera-Makefile/

###################################################################
# Project Configuration: 
# 
# Specify the name of the design (project) and the Quartus II
# Settings File (.qsf)
###################################################################

PROJECT ?= automake
ASSIGNMENT_FILES = $(SYN_DIR)/$(PROJECT).qpf $(SYN_DIR)/$(PROJECT).qsf

###################################################################
# Part, Family, Boardfile
FAMILY ?= 
PART ?= 
BOARDFILE ?= example_pins.qsf
###################################################################

###################################################################
# Setup your sources here
SRCS =

###################################################################
# Main Targets
#
# all: build everything
# clean: remove output files and database
# program: program your device with the compiled design
###################################################################

all: $(SYN_DIR)/smart.log $(PROJECT).asm.rpt $(PROJECT).sta.rpt $(PROJECT).eda.rpt diff

clean:
#$(PROJECT).qsf
	rm -rf \
	 $(SYN_DIR)/*.rpt \
	 $(SYN_DIR)/*.chg \
	 $(SYN_DIR)/smart.log \
	 $(SYN_DIR)/*.htm \
	 $(SYN_DIR)/*.eqn \
	 $(SYN_DIR)/*.pin \
	 $(SYN_DIR)/*.sof \
	 $(SYN_DIR)/*.pof \
	 $(SYN_DIR)/db \
	 $(SYN_DIR)/incremental_db

map: smart.log $(PROJECT).map.rpt
fit: smart.log $(PROJECT).fit.rpt
asm: smart.log $(PROJECT).asm.rpt
sta: smart.log $(PROJECT).sta.rpt
smart: smart.log
diff: $(WARNING_FILE)
	@echo "New warnings since previous build:"
	@diff --suppress-common-lines -T $(PREVIOUS_WARNINGS) $(WARNING_FILE) | sed -nr "s/>\t//p"

###################################################################
# Executable Configuration
###################################################################

#MAP_ARGS = --read_settings_files=on $(addprefix --source=../../,$(SRCS))
MAP_ARGS = --read_settings_files=on

FIT_ARGS = --part=$(DEVICE) --read_settings_files=on
ASM_ARGS =
STA_ARGS =
EDA_ARGS = --simulation --tool=modelsim --format=verilog

###################################################################
# Target implementations
###################################################################

STAMP = touch

$(PROJECT).map.rpt: $(SYN_DIR)/map.chg
	quartus_map $(MAP_ARGS) $(PROJECT)
	$(STAMP) $(SYN_DIR)/fit.chg

$(PROJECT).fit.rpt: $(SYN_DIR)/fit.chg $(PROJECT).map.rpt
	quartus_fit $(FIT_ARGS) $(PROJECT)
	$(STAMP) $(SYN_DIR)/asm.chg
	$(STAMP) $(SYN_DIR)/sta.chg

$(PROJECT).asm.rpt: $(SYN_DIR)/asm.chg $(PROJECT).fit.rpt
	quartus_asm $(ASM_ARGS) $(PROJECT)

$(PROJECT).sta.rpt: $(SYN_DIR)/sta.chg $(PROJECT).fit.rpt
	quartus_sta $(STA_ARGS) $(PROJECT)

$(PROJECT).eda.rpt: $(SYN_DIR)/eda.chg $(PROJECT).sta.rpt
	quartus_eda $(EDA_ARGS) $(PROJECT)

$(WARNING_FILE): $(PROJECT).map.rpt $(PROJECT).fit.rpt $(PROJECT).asm.rpt $(PROJECT).sta.rpt
	@touch $(WARNING_FILE)
	@cp $(WARNING_FILE) $(PREVIOUS_WARNINGS)
	$(PY) $(UTILS) warnings "$(PROJECT).map.rpt $(PROJECT).fit.rpt $(PROJECT).asm.rpt $(PROJECT).sta.rpt" $(WARNING_FILE)

# $(ASSIGNMENT_FILES)
$(SYN_DIR)/smart.log:
	quartus_sh -t $(PROJECT).tcl
#	quartus_sh --determine_smart_action $(PROJECT) > $(SYN_DIR)/smart.log

###################################################################
# Project initialization
###################################################################

$(ASSIGNMENT_FILES):
	echo $(TOP)
#	quartus_sh --prepare -f $(FAMILY) -t $(TOP) $(PROJECT).qpf
$(SYN_DIR)/map.chg:
	$(STAMP) $(SYN_DIR)/map.chg
$(SYN_DIR)/fit.chg:
	$(STAMP) $(SYN_DIR)/fit.chg
$(SYN_DIR)/sta.chg:
	$(STAMP) $(SYN_DIR)/sta.chg
$(SYN_DIR)/asm.chg:
	$(STAMP) $(SYN_DIR)/asm.chg
$(SYN_DIR)/eda.chg:
	$(STAMP) $(SYN_DIR)/eda.chg

###################################################################
# Programming the device
###################################################################

program: $(PROJECT).sof
	quartus_pgm --no_banner --mode=jtag -o "P;$(PROJECT).sof"
