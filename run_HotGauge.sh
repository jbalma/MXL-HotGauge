#!/bin/sh

outputDir= $1
instructionCount= $2 
hotGaugeHomeDir= $4

# if there is no value set for a parameter use the following
if [ -z $outputDir ]; then
  outputDir="/r/tcal/work/hotspot_share/perf_power_sims/thermalStackExperiments"
fi

if [ -z $instructionCount ]; then
  instructionCount="200000000"
fi

if [ -z $hotGaugeHomeDir ]; then
  hotGaugeHomeDir="/r/tcal/work/eabban01/HG_attempt4"
fi

echo '{"directory_format":"suite/workload/tech_node/frequency", "defaults":{"region":"start", "instruction_count":$instructionCount, "interval_ns":40000}}' | json_reformat > $outputDir/simulation_metadata.json

echo "sh /r/tcal/archgroup/archtools/sims/HotSniper/benchmarks/autoRunSniper.sh $outputDir $instructionCount $frequency"
benchmarks=("libquantum" "povray" "sphinx3" "gobmk" "astar")
directories=()

for benchmark in ${benchmarks[@]}; do
  for frequency in ${frequencies[@]}; do
        frequencyDir=$frequency
        frequencyDir+="GHz"
        dir="$outputDir/$benchmark/14nm/$frequencyDir/"
	directories+=("$dir")
  done
done

pushd $hotGaugeHomeDir/scripts > /dev/null 

mp_commands=()
for benchmark in ${benchmarks[@]}; do 
	command="sh 14_perf_sims_to_7_10_14_power_sims.sh $outputDir/spec-2006/$benchmark "
	mp_commands+=("$command")
	echo $command
	$command
done 

#rm mp_commands.txt || true

i=0
while [ $i -lt ${#mp_commands[@]} ]; do
  echo "${mp_commands[$i]}" >> mp_commands.txt
  ((i++))
done

echo "Now in $(pwd)"
#parallel < ../mp_commands.txt 
popd > /dev/null

#rm mp_commands.txt || true

