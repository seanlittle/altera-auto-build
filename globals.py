# the following entries should be present in the modelsim INI file (after using the quartus shell to compile the Altera
# libraries and then using the VMAP command to point modelsim to where these binaries are located)
precompiled_libraries = {'altera_mf_ver', 'altera_lnsim_ver', 'altera_ver', 'lpm_ver', 'sgate_ver', 'arriav_hssi_ver',
                         'arriav_pcie_hip_ver', 'arriav_ver', 'cyclonev_hssi_ver', 'cyclonev_pcie_hip_ver', 'cyclonev_ver',
                         'stratixv_hssi_ver', 'stratixv_pcie_hip_ver', 'stratixv_ver', 'twentynm_hip_ver', 'twentynm_hssi_ver',
                         'twentynm_ver'}

# want to be able to blackbox modules without modifiying the generated code; also want to map specific
# modules to their respective libraries in the Altera library structure
auto_bb_table = {
    'scfifo': 'altera_mf_ver',
    'dcfifo': 'altera_mf_ver',
    'dffeas': 'altera_ver',
    'altera_pll': 'altera_lnsim_ver',
    'altera_iopll': 'altera_lnsim_ver',
    'lpm_counter': 'lpm_ver',
    'twentynm_hssi_pma_aux': 'twentynm_hssi_ver',
    'twentynm_hssi_pma_uc': 'twentynm_hssi_ver',
    'twentynm_lcell_comb': 'twentynm_ver',
    'seriallite_iii_streaming': '~', # must include a TCL file for compilation
    'altera_xcvr_atx_pll_a10': '~',
    'altera_xcvr_reset_control': '~'}


def get_precompiled_libraries():
    return precompiled_libraries


def get_auto_bb_table():
    return auto_bb_table
