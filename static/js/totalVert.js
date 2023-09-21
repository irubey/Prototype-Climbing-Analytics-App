document.addEventListener("DOMContentLoaded", function() {
  function totalVertChart(targetId,userTicksData){
    //rendering functions
    const formatDate = d3.timeFormat('%Y-%m-%d');
    const parseDate = d3.timeParse('%Y-%m-%d');

    function transformData(data) {
        return data
            .filter(d => !isNaN(d.pitches) || d.length_category === 'multipitch')
            .map(d => ({
                date: parseDate(d.tick_date),
                seasonCategory: d.season_category.slice(0, -6),
                routeName: d.route_name,
                length: d.length === 0 ? null : d.length,
                pitches: d.length_category === 'multipitch' ? 1 : d.pitches
            }));  
    }

    function calculateAverageLength(data) {
        const averageLengthMap = new Map();
    
        data.forEach(d => {
            if (d.length !== null && !isNaN(d.length)) {
                const dateString = formatDate(d.date);
                if (!averageLengthMap.has(dateString)) {
                    averageLengthMap.set(dateString, { sum: d.length, count: 1 });
                } else {
                    const entry = averageLengthMap.get(dateString);
                    entry.sum += d.length;
                    entry.count++;
                }
            }
        });
    
        averageLengthMap.forEach((value, key) => {
            averageLengthMap.set(key, value.sum / value.count);
        });
        return averageLengthMap;
    }

    function calculateDailyVertical(data, averageLengthMap) {
        return data
            .map(d => {
                const dateString = formatDate(d.date);
                if (d.length === 0 || isNaN(d.length)) {
                    d.length = averageLengthMap.get(dateString);
                }
                return d;
            })
            .filter(d => d.length !== null && d.length !== undefined); 
    }

    function calculateTotalVertical(data) {
        const verticalMap = new Map();
    
        // Add the vertical (length * pitches) for each entry
        data.forEach(d => {
            d.vertical = d.length * d.pitches;
    
            const dateString = formatDate(d.date);
            const mapKey = `${dateString}_${d.seasonCategory}`; // Create a unique key
    
            if (!verticalMap.has(mapKey)) {
                verticalMap.set(mapKey, { total: d.vertical, seasonCategory: d.seasonCategory });
            } else {
                const current = verticalMap.get(mapKey);
                current.total += d.vertical;
            }
        });
    
        // Convert the map to the desired output format
        const output = [];
        verticalMap.forEach((value, key) => {
            const [dateString, _] = key.split('_');
            const dateObj = parseDate(dateString);
            output.push({ date: dateObj, totalVertical: value.total, seasonCategory: value.seasonCategory });
        });
    
        return output;
    } 

    function calcRunningTotalVertical(data){
        // Sort the data by date
        data.sort((a, b) => a.date - b.date);
        
        let accumulator = 0;
        const runningTotalVertical = data.map(d => {
            accumulator += d.totalVertical;
            return {
                date: d.date,
                runningTotalVertical: accumulator,
                seasonCategory: d.seasonCategory
            };
        });
    
        return runningTotalVertical;
    }

    function setupChart(targetId) {
        const margin = { top: 20, right: 20, bottom: 100, left: 80 };
        const width = 500 - margin.left - margin.right;
        const height = 300 - margin.top - margin.bottom;

        const svg = d3.select(targetId)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom);

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const color = d3.scaleOrdinal().range(d3.schemeSet2);
        
        // Using scaleTime for x-axis
        const x = d3.scaleTime().range([0, width]);

        const y = d3.scaleLinear().rangeRound([height, 0]);
        const z = color;

        return { svg, g, x, y, z, width, height, margin };
    }

    function generateLineChart(inputArray, targetId) {
        var { svg, g, x, y, z, width, height, margin } = setupChart(targetId);

        inputArray.forEach(d => {
            d.date = parseDate(formatDate(new Date(d.date)));
        });

        inputArray.sort((a, b) => a.date - b.date);

        x.domain([inputArray[0].date, inputArray[inputArray.length - 1].date]);
        y.domain([0, d3.max(inputArray, d => d.runningTotalVertical)]);

        const line = d3.line()
            .x(d => x(d.date))
            .y(d => y(d.runningTotalVertical))
            .curve(d3.curveMonotoneX);

        g.append("path")
            .datum(inputArray)
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 1.5)
            .attr("d", line);




        // X Axis
        const allMonths = inputArray.map(d => d.monthYear);
        const numTicks = 6;
        const tickInterval = Math.ceil(allMonths.length / numTicks);
        const tickValues = allMonths.filter((_, i) => i % tickInterval === 0);

        // X Axis
        g.append('g')
            .attr('class', 'x-axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x).ticks(d3.timeMonth.every(3)).tickFormat(d3.timeFormat("%B %Y")))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-65)");


        // Y-Axis
        g.append('g')
            .call(d3.axisLeft(y))
            .append('text')
                .attr('transform', 'rotate(-90)')
                .attr('y', 6)
                .attr('dy', '-5.5em')
                .attr('text-anchor', 'end')
                .attr('stroke', 'black')
                .attr('fill', 'black')
                .text('Running Total Vertical Feet');
    }

    d3.select(targetId).select("svg").remove();

    var discipline = d3.select("input[name='total-vert-discipline-filter']:checked").node().value;
    var timeFrame = d3.select("input[name='total-vert-time-filter']:checked").node().value;
    
    // Apply filters
    var filteredData = CommonFilters.filterByDiscipline(userTicksData, discipline);
    filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

    const transformedData = transformData(filteredData);
    const averageLengthMap = calculateAverageLength(transformedData);
    const updatedData = calculateDailyVertical(transformedData, averageLengthMap);
    const output = calculateTotalVertical(updatedData);
    const runningTotalVertical = calcRunningTotalVertical(output);

    generateLineChart(runningTotalVertical, targetId);
   }
  // Add event listeners to your filters
  d3.selectAll("input[name='total-vert-discipline-filter']").on('change', function() {
    totalVertChart('#total-vert', userTicksData);
   });
   
  d3.selectAll("input[name='total-vert-time-filter']").on('change', function(){
    totalVertChart('#total-vert', userTicksData);
   });

  totalVertChart('#total-vert', userTicksData); 
});