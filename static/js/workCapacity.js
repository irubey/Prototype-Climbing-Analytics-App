document.addEventListener("DOMContentLoaded", function() {
  function workCapacityChart(targetId, userTicksData){
    // Utilities
    console.log(userTicksData)
    const parseDate = d3.timeParse('%Y-%m-%d');
    const formatDate = d3.timeFormat('%Y-%m-%d');

    // Data Calcs
    function transformData(data) {
    return data
        .map(d => ({
            date: parseDate(d.tick_date), // Use the D3 function here
            seasonCategory: d.season_category,
            routeName: d.route_name,
            length: d.length === 0 ? null : d.length,
            pitches: d.length_category === 'multipitch' ? 1 : d.pitches
        }));
    }

    function calculateAverageLength(data) {
    const averageLengthMap = new Map();

    data.forEach(d => {
        if (d.length !== null && !isNaN(d.length)) {
            const dateString = formatDate(d.date); // Use the D3 function here
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

    // Rp up calculations:
    function calculateIncrementBySeason(data, discipline) {
        // Map discipline to the appropriate column name
        let column;
        switch (discipline) {
            case 'boulder':
                column = 'cur_max_boulder';
                break;
            case 'sport':
                column = 'cur_max_rp_sport';
                break;
            case 'trad':
                column = 'cur_max_rp_trad';
                break;
            default:
                console.error('Invalid discipline provided');
                return [];
    }

    // Filter out entries where the column value is 0
    const filteredData = data.filter(entry => entry[column] !== 0);

    // Group by seasonCategory and calculate the increment
    const groupedData = d3.group(filteredData, d => d.season_category);

    const increments = [];
    groupedData.forEach((entries, season) => {
        // Sort entries based on date to ensure we're checking increment in the correct order
        entries.sort((a, b) => a.tick_date.localeCompare(b.tick_date));

        const firstEntry = entries[0][column];
        const lastEntry = entries[entries.length - 1][column];

        if(firstEntry !== undefined && lastEntry !== undefined) {
            const incrementValue = lastEntry - firstEntry;
            increments.push({
                seasonCategory: season,
                increment: incrementValue
            });
        }
    });

    return increments;
    }

    //Chart setup and generation
    function setupChart(targetId) {
    const margin = { top: 20, right: 20, bottom: 100, left: 80 };
    const width = 500 - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    const svg = d3.select(targetId)
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom);
        // Removed the transform attribute here.

    const g = svg.append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    const color = d3.scaleOrdinal().range(d3.schemeSet2);
    const x = d3.scaleBand().rangeRound([0, width]).paddingInner(0.05).align(0.1);
    const y = d3.scaleLinear().rangeRound([height, 0]);
    const z = color;

    return { svg, g, x, y, z, width, height, margin };
    }

    function generateBarChart(data, targetId, increments) {
    // Compute average for each seasonCategory
    const averageData = Array.from(
        d3.rollup(data, 
                    group => ({
                        seasonCategory: group[0].seasonCategory,
                        averageVertical: d3.mean(group, d => d.totalVertical) || 0
                    }), 
                    d => d.seasonCategory
        ), 
        ([_, entry]) => entry
    );

    const { svg, g, x, y, z, width, height, margin } = setupChart(targetId);

    const earthTones = {
        0: "#8c8c8c",
        1: "#f2e1c1",
        2: "#d4bf91",
        3: "#bf9d6d",
        "4+": "#8c6f4b"
    };

    function getColorFromIncrement(increment) {
        return earthTones[increment] || earthTones[0];
    }

    const colorScale = d => {
        const incrementValue = increments.find(inc => inc.seasonCategory === d.seasonCategory);
        return incrementValue ? getColorFromIncrement(incrementValue.increment) : earthTones[0];
    };

    x.domain(averageData.map((d) => d.seasonCategory));
    y.domain([0, d3.max(averageData, (d) => d.averageVertical)]);

    g.selectAll('.bar')
        .data(averageData)
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', (d) => x(d.seasonCategory))
        .attr('y', (d) => y(d.averageVertical))
        .attr('width', x.bandwidth())
        .attr('height', (d) => height - y(d.averageVertical))
        .style('fill', colorScale)
        .style('stroke', 'black');

    // Map for incriment labels.
    const incrementLabels = {
        1: "+1 max grade",
        2: "+2 max grade",
        3: "+3 max grade",
        "4+": "+4 or more max grade"
    };

    g.selectAll('.bar-label')
    .data(averageData)
    .enter()
    .append('text')
    .attr('class', 'bar-label')
    .attr('transform', 'rotate(-90)')
    .attr('y', (d) => x(d.seasonCategory) + x.bandwidth() / 2)
    .attr('x', -1 * (height * 0.1 + margin.bottom))
    .attr('dy', '0.35em')  // This adjusts for centering the text within the bar. 0.35em is roughly half the size of the text.
    .style('text-anchor', 'middle')
    .style('fill', 'rgba(0, 0, 0, 0.6)')  // Semi-transparent black text
    .text(d => {
        const incrementValue = increments.find(inc => inc.seasonCategory === d.seasonCategory);
        if (incrementValue && incrementValue.increment > 0) {
            return incrementLabels[incrementValue.increment] || null;
        }
        return null;
    });





    g.append('g')
        .attr('transform', `translate(0, ${height})`)
        .call(d3.axisBottom(x).tickSizeOuter(0))
        .selectAll('text')
        .style('text-anchor', 'end')
        .attr('dx', '-.8em')
        .attr('dy', '.15em')
        .attr('transform', 'rotate(-65)');

    const yAxis = g.append('g').call(d3.axisLeft(y));
    yAxis.append('text')
            .attr('transform', 'rotate(-90)')
            .attr('y', 6)
            .attr('dy', '-5.5em')
            .attr('text-anchor', 'end')
            .attr('stroke', 'black')
            .attr('fill', 'black')
            .text('Average Daily Vertical Feet');

    }


    // Main Function
    function generateAverageVerticalChart(userTicksData, targetId) {
            
        d3.select(targetId).select("svg").remove();

        var discipline = d3.select("input[name='work-capacity-discipline-filter']:checked").node().value;
        var timeFrame = d3.select("input[name='work-capacity-time-filter']:checked").node().value;
        
        // Apply filters
        var filteredData = CommonFilters.filterByDiscipline(userTicksData, discipline);
        filteredData = CommonFilters.filterByTime(filteredData, timeFrame);
        const transformedData = transformData(filteredData);
        const averageLengthMap = calculateAverageLength(transformedData);
        const updatedData = calculateDailyVertical(transformedData, averageLengthMap);
        const output = calculateTotalVertical(updatedData);
        const increments = calculateIncrementBySeason(userTicksData, discipline); // Calculate increments

        generateBarChart(output, targetId, increments); // Pass increments to generateChart
    }

    generateAverageVerticalChart(userTicksData,targetId);
  }

  // Add event listeners to your filters
  d3.selectAll("input[name='work-capacity-discipline-filter']").on('change', function() {
    workCapacityChart('#work-capacity', userTicksData);
   });
   
  d3.selectAll("input[name='work-capacity-time-filter']").on('change', function(){
    workCapacityChart('#work-capacity', userTicksData);
   });

  workCapacityChart('#work-capacity', userTicksData); 
});
