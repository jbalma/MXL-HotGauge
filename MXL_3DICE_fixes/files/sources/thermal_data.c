/******************************************************************************
 * This file is part of 3D-ICE, version 3.0.0 .                               *
 *                                                                            *
 * 3D-ICE is free software: you can  redistribute it and/or  modify it  under *
 * the terms of the  GNU General  Public  License as  published by  the  Free *
 * Software  Foundation, either  version  3  of  the License,  or  any  later *
 * version.                                                                   *
 *                                                                            *
 * 3D-ICE is  distributed  in the hope  that it will  be useful, but  WITHOUT *
 * ANY  WARRANTY; without  even the  implied warranty  of MERCHANTABILITY  or *
 * FITNESS  FOR A PARTICULAR  PURPOSE. See the GNU General Public License for *
 * more details.                                                              *
 *                                                                            *
 * You should have  received a copy of  the GNU General  Public License along *
 * with 3D-ICE. If not, see <http://www.gnu.org/licenses/>.                   *
 *                                                                            *
 *                             Copyright (C) 2010                             *
 *   Embedded Systems Laboratory - Ecole Polytechnique Federale de Lausanne   *
 *                            All Rights Reserved.                            *
 *                                                                            *
 * Authors: Arvind Sridhar                                                    *
 *          Alessandro Vincenzi                                               *
 *          Giseong Bak                                                       *
 *          Martino Ruggiero                                                  *
 *          Thomas Brunschwiler                                               *
 *          Federico Terraneo                                                 *
 *          David Atienza                                                     *
 *                                                                            *
 * For any comment, suggestion or request  about 3D-ICE, please  register and *
 * write to the mailing list (see http://listes.epfl.ch/doc.cgi?liste=3d-ice) *
 * Any usage  of 3D-ICE  for research,  commercial or other  purposes must be *
 * properly acknowledged in the resulting products or publications.           *
 *                                                                            *
 * EPFL-STI-IEL-ESL                                                           *
 * Batiment ELG, ELG 130                Mail : 3d-ice@listes.epfl.ch          *
 * Station 11                                  (SUBSCRIPTION IS NECESSARY)    *
 * 1015 Lausanne, Switzerland           Url  : http://esl.epfl.ch/3d-ice.html *
 ******************************************************************************/

#include <stdio.h> // For the file type FILE
#include <stdlib.h> // MXL: malloc/free for the steady pluggable fixed point
#include <string.h> // MXL: memcpy
#include <math.h>   // MXL: fabs

#include "thermal_data.h"
#include "macros.h"

/******************************************************************************/

static Error_t init_data (double* data, uint32_t size, double init_value)
{
    while (size--) *data++ = init_value ;
    return TDICE_SUCCESS ;
}

int fpeek(FILE *stream)
{
    int c;
    c = fgetc(stream);
    ungetc(c, stream);
    return c;
}

int skip_comment_lines(FILE *stream)
{
    char comment_line[1000];
    while (fpeek(stream) == '%')
    {
        if (fgets(comment_line, sizeof comment_line, stream) == NULL)
        {
            return 1 ;
        }
    }
    return 0 ;
}

#ifndef PERMISSIVE_STACK_LOAD
int load_3d_grid_from_stream(FILE *input, double* data, double* next_temp, int* fscan_result, uint32_t size_0, uint32_t size_1, uint32_t size_2)
{
    int delimiter = 0 ;
    uint32_t counter = 0 ;
    uint32_t layer = 0 ;
    uint32_t row = 0 ;
    uint32_t column = 0 ;
    for (layer = 0; layer < size_0 ; layer++)
    {
        for (row = 0; row < size_1 ; row++)
        {
            for (column = 0; column < size_2 ; column++)
            {
                if (*fscan_result == EOF)
                    return counter ;
                *data++ = *next_temp ;
                counter++ ;
                delimiter = getc (input) ;
                if ((column < size_2 - 1) && (delimiter != ' '))
                {
                    fprintf(stderr, "In column:%d/%d row:%d/%d, layer:%d/%d\n", column+1, size_2, row+1, size_1, layer+1, size_0) ;
                    fprintf(stderr, "Expected :space: delimiter but got :%c:\n", delimiter) ;
                    return counter;
                }
                *fscan_result = fscanf(input,"%lf", next_temp) ;
            }
            if (*fscan_result == EOF)
                return counter ;
            if ((row < size_1 - 1) && (delimiter != '\t'))
            {
               fprintf(stderr, "In column:%d/%d row:%d/%d, layer:%d/%d\n", 1, size_2, row+1, size_1, layer+1, size_0) ;
               fprintf(stderr, "Expected :tab: delimiter but got :%c:\n", delimiter) ;
               return counter;
            }
        }
        if (*fscan_result == EOF)
            return counter ;
        if (delimiter != '\n')
        {
            fprintf(stderr, "In column:%d/%d row:%d/%d, layer:%d/%d\n", 1, size_2, 1, size_1, layer+1, size_0) ;
            fprintf(stderr, "Expected :new line: delimiter but got :%c:\n", delimiter) ;
            return counter ;
        }
    }
    return counter ;
}
#endif

#ifdef PERMISSIVE_STACK_LOAD
static Error_t init_data_from_file (double* data, uint32_t size, String_t file_name)
{
    fprintf (stdout, "Loading %s\n", file_name) ; fflush (stdout) ;
#else
static Error_t init_data_from_file_strict (double* data, uint32_t size_0, uint32_t size_1, uint32_t size_2, uint32_t extra_size_1, uint32_t extra_size_2, String_t file_name)
{
    fprintf (stdout, "Loading and validating %s\n", file_name) ; fflush (stdout) ;
#endif
    FILE* input = fopen(file_name, "r") ;
    double next_temp ;
    int fscan_result ;
    unsigned int counter = 0 ;
#ifndef PERMISSIVE_STACK_LOAD
    unsigned int values_read ;
    unsigned int extra_size_0 = 1 ;
    unsigned int size_stk = size_0 * size_1 * size_2 ;
    unsigned int size_sink = extra_size_0 * extra_size_1 * extra_size_2 ;
    unsigned int size = size_stk + size_sink ;
#endif
    // Allow for comment(s) at the beginning of the file
    if (skip_comment_lines (input) != 0)
    {
        // A file read error occurred while trying to skip comment lines
        return TDICE_FAILURE ;
    }

    fscan_result = fscanf(input,"%lf", &next_temp) ;
#ifdef PERMISSIVE_STACK_LOAD
    while ((counter < size) && (fscan_result != EOF))
    {
        *data++ = next_temp ;
        counter++;
        // Let fscanf gobble up any whitespace delimiters
        fscan_result = fscanf(input,"%lf", &next_temp) ;
    }
#else
    fprintf(stdout, "Loading stack layers...\n") ; fflush (stdout) ;
    values_read = load_3d_grid_from_stream(input, data, &next_temp, &fscan_result, size_0, size_1, size_2) ;
    if (values_read < size_stk)
    {
        fclose(input) ;
       return TDICE_FAILURE ;
    }
    counter += values_read ;
    data += values_read ; // The pointer isn't incremented by load_3d_grid_from_stream

    if (size_sink > 0)
    {
        fprintf(stdout, "Loading extra_sink layers...\n") ; fflush (stdout) ;
        values_read = load_3d_grid_from_stream(input, data, &next_temp, &fscan_result, extra_size_0, extra_size_1, extra_size_2) ;
        if (values_read < size_sink)
        {
            fclose(input) ;
            return TDICE_FAILURE ;
        }
        counter += values_read ;
        data += values_read ; // The pointer isn't incremented by load_3d_grid_from_stream
    }
#endif
    if (fscan_result != EOF)
    {
        // There are more tokens left in the file.. something is wrong..
        int extra_tokens = 1 ;
        while (fscanf(input,"%lf", &next_temp) != EOF)
            extra_tokens += 1 ;
        fclose(input) ;
        fprintf(stderr, "Error: %s had %d more values than the expected %d\n", file_name, extra_tokens, size) ;
        return TDICE_FAILURE ;
    }
    else if (counter < size)
    {
        // There were less values read than expected.. something is wrong..
        fclose(input) ;
        fprintf(stderr, "Error: %s had %d values but %d were expected\n", file_name, counter, size) ;
        return TDICE_FAILURE ;
    }
    fclose(input) ;
    return TDICE_SUCCESS ;
}

/******************************************************************************/

void thermal_data_init (ThermalData_t *tdata)
{
    tdata->Size = (CellIndex_t) 0u ;

    tdata->Temperatures = NULL ;

    thermal_grid_init  (&tdata->ThermalGrid) ;
    power_grid_init    (&tdata->PowerGrid) ;
    system_matrix_init (&tdata->SM_A) ;

    tdata->SLUMatrix_B.Store = NULL ;
}

/******************************************************************************/

Error_t thermal_data_build
(
    ThermalData_t      *tdata,
    StackElementList_t *stack_elements_list,
    Dimensions_t       *dimensions,
    Analysis_t         *analysis
)
{
    Error_t result ;

    tdata->Size = get_number_of_cells (dimensions) ;

    /* Alloc and fill the thermal grid */

    result = thermal_grid_build (&tdata->ThermalGrid, dimensions) ;

    if (result == TDICE_FAILURE)
    {
        fprintf (stderr, "Cannot malloc thermal grid\n") ;

        return TDICE_FAILURE ;
    }

    result = thermal_grid_fill (&tdata->ThermalGrid, stack_elements_list) ;

    if (result == TDICE_FAILURE)
    {
        return TDICE_FAILURE ;
    }

    /* Alloc and set temperatures */

    tdata->Temperatures =

        (Temperature_t*) malloc (sizeof(Temperature_t) * tdata->Size) ;

    if (tdata->Temperatures == NULL)
    {
        fprintf (stderr, "Cannot malloc temperature array\n") ;

        return TDICE_FAILURE ;
    }

    /* Set Temperatures to the initial thermal state and builds SLU vector B */

    result = reset_thermal_state (tdata, dimensions, analysis) ;
    if (result == TDICE_FAILURE)
    {
        fprintf (stderr, "Failed to reset thermal state\n") ;

        free (tdata->Temperatures) ;

        return TDICE_FAILURE ;
    }

    dCreate_Dense_Matrix  /* Vector B */

        (&tdata->SLUMatrix_B, tdata->Size, 1,
         tdata->Temperatures, tdata->Size,
         SLU_DN, SLU_D, SLU_GE) ;


    /* Alloc and fill the power grid */

    result = power_grid_build (&tdata->PowerGrid, dimensions) ;

    if (result == TDICE_FAILURE)
    {
        fprintf (stderr, "Cannot malloc power grid\n") ;

        Destroy_SuperMatrix_Store (&tdata->SLUMatrix_B) ;

        free (tdata->Temperatures) ;

        thermal_grid_destroy (&tdata->ThermalGrid) ;

        return TDICE_FAILURE ;
    }

    power_grid_fill

        (&tdata->PowerGrid, &tdata->ThermalGrid, stack_elements_list, dimensions) ;

    /* Alloc and fill the system matrix and builds the SLU wrapper */

    result = system_matrix_build

        (&tdata->SM_A, tdata->Size, get_number_of_connections (dimensions)) ;

    if (result == TDICE_FAILURE)
    {
        fprintf (stderr, "Cannot malloc syatem matrix\n") ;

        Destroy_SuperMatrix_Store (&tdata->SLUMatrix_B) ;

        free (tdata->Temperatures) ;

        thermal_grid_destroy (&tdata->ThermalGrid) ;
        power_grid_destroy   (&tdata->PowerGrid) ;

        return TDICE_FAILURE ;
    }

    fill_system_matrix

        (&tdata->SM_A, &tdata->ThermalGrid, analysis, dimensions) ;

    result = do_factorization (&tdata->SM_A) ;

    if (result == TDICE_FAILURE)
    {
        thermal_data_destroy (tdata) ;

        return TDICE_FAILURE ;
    }

    return TDICE_SUCCESS ;
}

/******************************************************************************/

void thermal_data_destroy (ThermalData_t *tdata)
{
    free (tdata->Temperatures) ;

    thermal_grid_destroy (&tdata->ThermalGrid) ;
    power_grid_destroy   (&tdata->PowerGrid) ;

    system_matrix_destroy (&tdata->SM_A) ;

    Destroy_SuperMatrix_Store (&tdata->SLUMatrix_B) ;

    thermal_data_init (tdata) ;
}

/******************************************************************************/

Error_t reset_thermal_state (ThermalData_t *tdata, Dimensions_t *dimensions, Analysis_t *analysis)
{
    unsigned int sink_rows = 0 ;
    unsigned int sink_columns = 0 ;
    if (tdata->ThermalGrid.TopHeatSink && tdata->ThermalGrid.TopHeatSink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE)
    {
       sink_rows = tdata->ThermalGrid.TopHeatSink->NRows ;
       sink_columns = tdata->ThermalGrid.TopHeatSink->NColumns ;
    }
    unsigned int layers = last_layer (dimensions) + 1;
    unsigned int rows = last_row (dimensions) + 1;
    unsigned int columns = last_column (dimensions) + 1;
    unsigned int expected_size = layers * rows * columns + sink_rows*sink_columns;

    if (tdata->Size != expected_size )
    {
        fprintf(stderr, "Something went wrong... tdata size(%d) does not match expected dimension size(%d)\n", tdata->Size, expected_size) ;
        return TDICE_FAILURE ;
    }
    if (analysis->InitialTemperatureFile == NULL)
        return init_data (tdata->Temperatures, tdata->Size, analysis->InitialTemperature) ;
    else
    {
#ifdef PERMISSIVE_STACK_LOAD
        return init_data_from_file (tdata->Temperatures, tdata->Size, analysis->InitialTemperatureFile) ;
#else
        return init_data_from_file_strict (tdata->Temperatures, layers, rows, columns, sink_rows, sink_columns, analysis->InitialTemperatureFile) ;
#endif
   }
}

/******************************************************************************/

static void fill_system_vector
(
    Dimensions_t  *dimensions,
    HeatSink_t    *topSink,
    double        *vector,
    Source_t      *sources,
    Capacity_t    *capacities,
    Temperature_t *temperatures,
    Time_t         step_time
)
{
#ifdef PRINT_SYSTEM_VECTOR
    Temperature_t old ;
#endif

    CellIndex_t layer ;
    CellIndex_t row ;
    CellIndex_t column ;

    for (layer = first_layer (dimensions) ; layer <= last_layer (dimensions) ; layer++)
    {
        for (row = first_row (dimensions) ; row <= last_row (dimensions) ; row++)
        {
            for (column = first_column (dimensions) ; column <= last_column (dimensions) ; column++)
            {

#ifdef PRINT_SYSTEM_VECTOR
                old = *temperatures ;
#endif

                *vector++ = *sources++
                            + (*capacities++ / step_time)
                              * *temperatures++ ;

#ifdef PRINT_SYSTEM_VECTOR
                fprintf (stderr,
                    " l %2d r %4d c %4d [%7d] | %e [b] = %e [s] + %e [c] * %e [t]\n",
                    layer, row, column,
                    get_cell_offset_in_stack (dimensions, layer, row, column),
                    *(vector-1), *(sources-1), *(capacities-1), old) ;
#endif

            } // FOR_EVERY_COLUMN
        } // FOR_EVERY_ROW
    } // FOR_EVERY_LAYER

    // Copy the rest of the vector
    if(topSink && topSink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE)
    {
        for(row = 0; row < topSink->NRows; row++)
        {
            for(column = 0; column < topSink->NColumns; column++)
            {
#ifdef PRINT_SYSTEM_VECTOR
                old = *temperatures ;
#endif

                *vector++ = *sources++
                            + (*capacities++ / step_time)
                              * *temperatures++ ;

#ifdef PRINT_SYSTEM_VECTOR
                fprintf (stderr,
                    "      r %4d c %4d [%7d] | %e [b] = %e [s] + %e [c] * %e [t]\n",
                    row, column,
                    get_spreader_cell_offset (dimensions, topSink, row, column),
                    *(vector-1), *(sources-1), *(capacities-1), old) ;
#endif
            }
        }
    }
}

/******************************************************************************/

// MXL: steady state with a pluggable heat sink -- PARTIAL. Read this before relying on it.
//
// Upstream refuses the combination outright, and the TODO it left ("support steady state
// pluggable sink") understates why. Three things stand in the way and only two are fixed here.
//
// 1. FIXED. This function walked only the chip layers. The transient fill_system_vector has an
//    extra block copying the spreader cells; without the same here the spreader rows of the
//    system vector were never written at all.
//
// 2. FIXED. The plugin returns a heat flow computed FROM the spreader temperature it is handed,
//    so sources depend on temperatures and one linear solve cannot close it. That is a fixed
//    point, the same shape as the leakage feedback this project runs one level up, and it is
//    solved the same way -- iterate until the field stops moving.
//
// 3. NOT FIXED, and it is the real blocker. Spreader cells have NO conductance to ambient: the
//    plugin contributes heat as a source term, never as a matrix coefficient. In transient the
//    capacity/StepTime term on the spreader diagonal (system_matrix.c, "if TRANSIENT") keeps the
//    system non-singular. In steady that term is zero, so the spreader block couples only to its
//    neighbours and the assembled matrix is singular -- a pure Neumann problem with no Dirichlet
//    reference anywhere in it. SuperLU returns NaN.
//
// The fix for (3) is to linearise the plugin into the matrix rather than the right-hand side:
// probe it at two uniform temperatures to recover g and T_ambient from Q = g (T - T_ambient),
// add g to the spreader diagonal and g*T_ambient to the source. For a LINEAR plugin -- which a
// fixed-resistance cooling boundary is -- that is exact, needs no iteration at all, and preserves
// the factorisation so the session cache still works. It requires touching system_matrix.c and
// storing the probed coefficients on the sink, which is a larger change than this one.
//
// Until then this path detects the singularity and says so, instead of iterating 200 times on
// NaN or handing back a plausible-looking field.
#define MXL_STEADY_PLUGGABLE_MAX_ITER 200u
#define MXL_STEADY_PLUGGABLE_TOL      1.0e-4   /* K; the field is in kelvin */

static void fill_system_vector_steady
(
    Dimensions_t *dimensions,
    double       *vector,
    Source_t     *sources,
    HeatSink_t   *topSink
)
{
    CellIndex_t layer ;
    CellIndex_t row ;
    CellIndex_t column ;

    for (layer = first_layer (dimensions) ; layer <= last_layer (dimensions) ; layer++)
    {
        for (row = first_row (dimensions) ; row <= last_row (dimensions) ; row++)
        {
            for (column = first_column (dimensions) ; column <= last_column (dimensions) ; column++)
            {
                *vector++ =   *sources++ ;

#ifdef PRINT_SYSTEM_VECTOR
                fprintf (stderr,
                    " l %2d r %4d c %4d [%7d] | %e [b] = %e [s]\n",
                    layer, row, column,
                    get_cell_offset_in_stack (dimensions, layer, row, column),
                    *(vector-1), *(sources-1)) ;
#endif

            } // FOR_EVERY_COLUMN
        } // FOR_EVERY_ROW
  } // FOR_EVERY_LAYER

    // MXL: the spreader cells, which only exist under the pluggable model. Steady state has no
    // capacitance term, so unlike the transient path this is just the source.
    if (topSink != NULL && topSink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE)
    {
        CellIndex_t srow, scolumn ;

        for (srow = 0 ; srow < topSink->NRows ; srow++)
        {
            for (scolumn = 0 ; scolumn < topSink->NColumns ; scolumn++)
            {
                *vector++ = *sources++ ;
            }
        }
    }
}

Error_t pluggable_heatsink(ThermalData_t *tdata, Dimensions_t *dimensions)
{
    // We have something to do only if we're using the pluggable heatsink model
    HeatSink_t *sink = tdata->ThermalGrid.TopHeatSink;
    if(sink == NULL || sink->SinkModel != TDICE_HEATSINK_TOP_PLUGGABLE)
            return TDICE_SUCCESS;

    //Get a pointer to the spreader temperatures
    double *SpreaderTemperatures = tdata->Temperatures;
    SpreaderTemperatures += get_spreader_cell_offset(dimensions,sink,0,0);

    Source_t *sources = tdata->PowerGrid.Sources;
    sources += get_spreader_cell_offset(dimensions,sink,0,0);

    // Call the pluggable heat sink function to compute the heat flows to
    // the heatsink
    if(sink->PluggableHeatsink(SpreaderTemperatures,sources))
    {
        fprintf(stderr, "Error: pluggable heatsink callback failed\n");
        return TDICE_FAILURE;
    }

    // Both 3D-ICE and plugin use passive sign convention
    unsigned int size = sink->NColumns * sink->NRows;
    unsigned int i;
    for(i = 0; i < size; i++)
        sources[i] = - sources[i];

    return TDICE_SUCCESS;
}

/******************************************************************************/

SimResult_t emulate_step
(
    ThermalData_t  *tdata,
    Dimensions_t   *dimensions,
    Analysis_t     *analysis
)
{
    if (analysis->AnalysisType != TDICE_ANALYSIS_TYPE_TRANSIENT)

        return TDICE_WRONG_CONFIG ;

    if (slot_completed (analysis) == true)
    {
        Error_t result = update_source_vector (&tdata->PowerGrid, dimensions) ;

        if (result == TDICE_FAILURE)

            return TDICE_END_OF_SIMULATION ;
    }

    if(pluggable_heatsink(tdata, dimensions) == TDICE_FAILURE)
        return TDICE_SOLVER_ERROR ;

    fill_system_vector

        (dimensions, tdata->ThermalGrid.TopHeatSink, tdata->Temperatures, tdata->PowerGrid.Sources,
         tdata->PowerGrid.CellsCapacities, tdata->Temperatures, analysis->StepTime) ;

    Error_t res = solve_sparse_linear_system (&tdata->SM_A, &tdata->SLUMatrix_B) ;

    if (res != TDICE_SUCCESS)

        return TDICE_SOLVER_ERROR ;

    increase_by_step_time (analysis) ;

    if (slot_completed (analysis) == false)

        return TDICE_STEP_DONE ;

    else

        return TDICE_SLOT_DONE ;
}

/******************************************************************************/

SimResult_t emulate_slot
(
    ThermalData_t  *tdata,
    Dimensions_t   *dimensions,
    Analysis_t     *analysis
)
{
    SimResult_t result ;

    do
    {

        result = emulate_step (tdata, dimensions, analysis) ;

    }   while (result == TDICE_STEP_DONE) ;

    return result ;
}

/******************************************************************************/

SimResult_t emulate_steady
(
    ThermalData_t  *tdata,
    Dimensions_t   *dimensions,
    Analysis_t     *analysis
)
{
    if (analysis->AnalysisType != TDICE_ANALYSIS_TYPE_STEADY)

        return TDICE_WRONG_CONFIG ;

    HeatSink_t *mxl_sink = tdata->ThermalGrid.TopHeatSink ;
    int mxl_pluggable = (mxl_sink != NULL
                         && mxl_sink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE) ;

    Error_t result = update_source_vector (&tdata->PowerGrid, dimensions) ;

    if (result == TDICE_FAILURE)
    {
        fprintf (stderr,

            "Warning: no power trace given for steady state simulation\n") ;

        return TDICE_END_OF_SIMULATION ;
    }

    if (mxl_pluggable == 0)
    {
        fill_system_vector_steady (dimensions, tdata->Temperatures,
                                   tdata->PowerGrid.Sources, NULL) ;

        Error_t res = solve_sparse_linear_system (&tdata->SM_A, &tdata->SLUMatrix_B) ;

        if (res != TDICE_SUCCESS)

            return TDICE_SOLVER_ERROR ;

        return TDICE_END_OF_SIMULATION ;
    }

    // MXL: pluggable sink. Iterate sources <-> temperatures to a fixed point. The plugin is
    // called with the CURRENT field, so `prev` must be taken before fill_system_vector_steady
    // overwrites Temperatures with the right-hand side.
    {
        double      *mxl_prev = (double *) malloc (tdata->Size * sizeof (double)) ;
        SimResult_t  mxl_out  = TDICE_SOLVER_ERROR ;
        unsigned int mxl_iter ;

        if (mxl_prev == NULL)
        {
            fprintf (stderr, "Error: out of memory in steady pluggable solve\n") ;

            return TDICE_SOLVER_ERROR ;
        }

        for (mxl_iter = 0 ; mxl_iter < MXL_STEADY_PLUGGABLE_MAX_ITER ; mxl_iter++)
        {
            Quantity_t mxl_i ;
            double     mxl_worst = 0.0 ;

            memcpy (mxl_prev, tdata->Temperatures, tdata->Size * sizeof (double)) ;

            if (update_source_vector (&tdata->PowerGrid, dimensions) == TDICE_FAILURE)

                break ;

            if (pluggable_heatsink (tdata, dimensions) == TDICE_FAILURE)

                break ;

            fill_system_vector_steady (dimensions, tdata->Temperatures,
                                       tdata->PowerGrid.Sources, mxl_sink) ;

            if (solve_sparse_linear_system (&tdata->SM_A, &tdata->SLUMatrix_B) != TDICE_SUCCESS)

                break ;

            // A singular matrix shows up here as NaN rather than as a solver error, so it has
            // to be caught explicitly -- otherwise the loop runs to its iteration limit and the
            // failure gets misreported as non-convergence.
            for (mxl_i = 0 ; mxl_i < tdata->Size ; mxl_i++)
            {
                if (tdata->Temperatures[mxl_i] != tdata->Temperatures[mxl_i])
                {
                    fprintf (stderr,
                        "Error: steady solve with a pluggable heat sink produced NaN. The "
                        "spreader cells have no conductance to ambient -- the plugin supplies "
                        "heat as a source, and without the transient capacity term on the "
                        "diagonal the system matrix is singular. See the note above "
                        "fill_system_vector_steady.\n") ;

                    free (mxl_prev) ;

                    return TDICE_SOLVER_ERROR ;
                }

                double mxl_d = fabs (tdata->Temperatures[mxl_i] - mxl_prev[mxl_i]) ;

                if (mxl_d > mxl_worst) mxl_worst = mxl_d ;
            }

            if (mxl_iter > 0 && mxl_worst < MXL_STEADY_PLUGGABLE_TOL)
            {
                mxl_out = TDICE_END_OF_SIMULATION ;

                break ;
            }
        }

        free (mxl_prev) ;

        if (mxl_out != TDICE_END_OF_SIMULATION)

            fprintf (stderr,
                "Error: steady pluggable heatsink did not reach a fixed point in %u iterations\n",
                MXL_STEADY_PLUGGABLE_MAX_ITER) ;

        return mxl_out ;
    }
}

/******************************************************************************/

Error_t update_coolant_flow_rate
(
    ThermalData_t  *tdata,
    Dimensions_t   *dimensions,
    Analysis_t     *analysis,
    CoolantFR_t     new_flow_rate
)
{
    tdata->ThermalGrid.Channel->Coolant.FlowRate =

        FLOW_RATE_FROM_MLMIN_TO_UM3SEC(new_flow_rate) ;

    // TODO replace with "update"

    fill_system_matrix (&tdata->SM_A, &tdata->ThermalGrid, analysis, dimensions) ;

    if (do_factorization (&tdata->SM_A) == TDICE_FAILURE)

        return TDICE_FAILURE ;

    update_channel_sources (&tdata->PowerGrid, dimensions) ;

    return TDICE_SUCCESS ;
}

/******************************************************************************/

Temperature_t get_cell_temperature
(
    ThermalData_t *tdata,
    Dimensions_t  *dimensions,
    CellIndex_t    layer_index,
    CellIndex_t    row_index,
    CellIndex_t    column_index
)
{
    CellIndex_t id = get_cell_offset_in_stack

                     (dimensions, layer_index, row_index, column_index) ;

    if (id >= get_number_of_cells (dimensions))

        return 0.0 ;

    else

        return *(tdata->Temperatures + id) ;
}

/******************************************************************************/

Error_t print_thermal_map
(
    ThermalData_t      *tdata,
    StackElementList_t *list,
    Dimensions_t       *dimensions,
    String_t            stack_element_id,
    String_t            file_name
)
{
    StackElement_t stkel ;

    stack_element_init (&stkel) ;

    string_copy (&stkel.Id, &stack_element_id) ;

    StackElement_t *tmp = stack_element_list_find (list, &stkel) ;

    if (tmp == NULL)
    {
        stack_element_destroy (&stkel) ;

        return TDICE_FAILURE ;
    }

    stack_element_destroy (&stkel) ;

    FILE *output_file = fopen (file_name, "w") ;

    if (output_file == NULL)
    {
        fprintf (stderr, "Unable to open output file %s\n", file_name) ;

        return TDICE_FAILURE ;
    }

    stack_element_print_thermal_map

        (tmp, dimensions, tdata->Temperatures, output_file) ;

    fclose (output_file) ;

    return TDICE_SUCCESS ;
}

/******************************************************************************/

void thermal_data_print_stack
(
    Dimensions_t    *dimensions,
    HeatSink_t      *topSink,
    Temperature_t   *temperatures,
    FILE            *stream
)
{


    CellIndex_t layer ;
    CellIndex_t row ;
    CellIndex_t column ;

    for (layer = first_layer (dimensions) ; layer <= last_layer (dimensions) ; layer++)
    {
        for (row = first_row (dimensions) ; row <= last_row (dimensions) ; row++)
        {
            for (column = first_column (dimensions) ; column <= last_column (dimensions) ; column++)
            {
                fprintf (stream, "%7.3f", *temperatures++) ;
                if (column < last_column (dimensions))
                   fprintf(stream, " ") ;
            } // FOR_EVERY_COLUMN
            if (row < last_row (dimensions))
               fprintf (stream, "\t") ;
        } // FOR_EVERY_ROW
        if (layer < last_layer (dimensions))
            fprintf (stream, "\n") ;
    } // FOR_EVERY_LAYER

    // When using the pluggable heatsink there are additional cells for the heat spreader
    if(topSink && topSink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE)
    {
        fprintf (stream, "\n") ;
        for (row = 0 ; row < topSink->NRows ; row++)
        {
            for (column = 0 ; column < topSink->NColumns ; column++)
            {
                fprintf (stream, "%7.3f", *temperatures++) ;
                if (column < topSink->NColumns - 1)
                   fprintf(stream, " ") ;
            } // FOR_EVERY_COLUMN
            if (row < topSink->NRows -1)
                fprintf (stream, "\t") ;
        } // FOR_EVERY_ROW
    fprintf (stream, "\n") ;
    } // IF TDICE_HEATSINK_TOP_PLUGGABLE
}
