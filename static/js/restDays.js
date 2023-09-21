document.addEventListener("DOMContentLoaded", function() {
    //rendering function
    function restDaysChart(targetElement, userTicksData) {
        d3.select(targetElement).select("svg").remove();

        var discipline = d3.select("input[name='rest-days-discipline-filter']:checked").node().value;
        var timeFrame = d3.select("input[name='rest-days-time-filter']:checked").node().value;
        
        // Apply filters
        var filteredData = CommonFilters.filterByDiscipline(userTicksData, discipline);
        filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

        // 1. Pre-process data
        const monthsData = filteredData.reduce((acc, tick) => {
        const date = new Date(tick.tick_date);
        if (!isNaN(date)) {
            const monthYearKey = `${date.getMonth() + 1}-${date.getFullYear()}`; // e.g., "4-2023"
            if (!acc[monthYearKey]) {
            acc[monthYearKey] = new Set();
            }
            acc[monthYearKey].add(date.toISOString().slice(0, 10)); // Add unique day to set
        }
        return acc;
        }, {});
    
        // 2. Compute average climbing days
        const averageClimbingDays = Object.entries(monthsData).map(([monthYear, daysSet]) => {
        const [month, year] = monthYear.split('-').map(Number);
        const totalDaysInMonth = new Date(year, month, 0).getDate();
        const weeksInMonth = totalDaysInMonth / 7;
        const averageClimbing = daysSet.size / weeksInMonth;
    
        return {
            monthYear,
            averageClimbing,
            averageRest: 7 - averageClimbing,
        };
        });
    
        // 3. Visualize data
        // Define margins and dimensions
        const margin = { top: 20, right: 20, bottom: 50, left: 40 };
        const width = 650 - margin.left - margin.right;
        const height = 400 - margin.top - margin.bottom;

        //Legend Mapping
        const legendMapping = {
            averageClimbing: 'Rock Climbing',
            averageRest: 'Rest/Gym'
        };        
    
        // Scales
        const x = d3.scaleBand()
        .domain(averageClimbingDays.map(d => d.monthYear))
        .range([0, width])
        .padding(0.2);
    
        const y = d3.scaleLinear()
        .domain([0, 7])
        .range([height, 0]);
    
        const color = d3.scaleOrdinal()
        .domain(['averageClimbing', 'averageRest'])
        .range(['#58D68D', '#CDCFD3']);
    
        // SVG canvas
        const svg = d3.select(targetElement)
        .append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
        // Create stacked data
        const stackGen = d3.stack()
        .keys(['averageClimbing', 'averageRest'])
        .order(d3.stackOrderNone)
        .offset(d3.stackOffsetNone);
    
        const stackedData = stackGen(averageClimbingDays);
    
        svg.selectAll('g.layer')
            .data(stackedData)
            .join('g')
            .attr('class', 'layer')
            .attr('fill', d => color(d.key))
            .selectAll('rect')
            .data(d => d)
            .join('rect')
            .attr('x', d => x(d.data.monthYear))
            .attr('y', d => y(d[1]))
            .attr('height', d => y(d[0]) - y(d[1]))
            .attr('width', x.bandwidth());
    
        // X Axis
        const allMonths = averageClimbingDays.map(d => d.monthYear);
        const numTicks = 6;
        const tickInterval = Math.ceil(allMonths.length / numTicks);
        const tickValues = allMonths.filter((_, i) => i % tickInterval === 0);

        svg.append('g')
            .attr('class', 'x-axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x).tickValues(tickValues))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-65)");

        // Y Axis

        // Determine the height between two ticks
        const tickSpacing = y(0) - y(1);

        // Modify the y-axis
        svg.append('g')
            .attr('class', 'y-axis')
            .call(d3.axisLeft(y).tickSize(-width).tickFormat(d3.format("d")).tickValues([1, 2, 3, 4, 5, 6, 7]))
            .selectAll(".tick text")
            .attr("transform", "translate(0," + (tickSpacing / 2) + ")");

        
        svg.selectAll('.y-axis .tick line')
            .attr('stroke-dasharray', '2,2')  // This makes them dashed; remove or adjust for different styles
            .attr('opacity', 0.6);  // Adjusts the opacity; set to 1 for full opacity

    

        // Legend
        const legend = svg.append('g')
        .attr('transform', `translate(${width - 100},10)`);
    
        ['averageClimbing', 'averageRest'].forEach((key, idx) => {
            const legendRow = legend.append('g')
                .attr('transform', `translate(0, ${idx * 20})`);
        
            legendRow.append('rect')
                .attr('width', 10)
                .attr('height', 10)
                .attr('fill', color(key));
        
            legendRow.append('text')
                .attr('x', -10)
                .attr('y', 10)
                .attr('text-anchor', 'end')
                .style('text-transform', 'capitalize')
                .text(legendMapping[key]);
        });
        
    }
  
    // Add event listeners to your filters
    d3.selectAll("input[name='rest-days-discipline-filter']").on('change', function() {
        restDaysChart('#rest-days', userTicksData);
     });
     
    d3.selectAll("input[name='rest-days-time-filter']").on('change', function(){
        restDaysChart('#rest-days', userTicksData);
     });

    restDaysChart('#rest-days', userTicksData); 
});