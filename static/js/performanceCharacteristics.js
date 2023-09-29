document.addEventListener("DOMContentLoaded", function() {
    function characterVizChart(characteristicsId, lengthId, styleId, inputData, binnedCodeDict){
        //Setup
        function getGradeForCode(binnedCode) {
            const entry = binnedCodeDict.find(item => item.binned_code === binnedCode);
            return entry ? entry.binned_grade : binnedCode;
        }
        
        function setupChart(targetId) {
            const margin = { top: 20, right: 20, bottom: 80, left: 80 };
            const width = 500 - margin.left - margin.right;
            const height = 300 - margin.top - margin.bottom;
        
            const svg = d3.select(targetId)
                .append("svg")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom);
                // Removed the transform attribute here.
        
            const g = svg.append("g")
                .attr("transform", `translate(${margin.left},${margin.top})`);
        

            const color = d3.scaleOrdinal().range(["#0078D4", "#F25022", "#7CBB00", "#FFB900"]);

            const x = d3.scaleBand().rangeRound([0, width]).paddingInner(0.05).align(0.1);
            const y = d3.scaleLinear().rangeRound([height, 0]);
            const z = color;
        
            return { svg, g, x, y, z, width, height, margin };
        }
        
        function drawBarsAndAxes({ svg, g, x, y, z, width, height, margin, dataset, keys, attribute }) {
            // Set y domain based on the max count across all groups and attributes
            y.domain([0, d3.max(dataset, d => keys.reduce((acc, key) => acc + (d[key] || 0), 0))]).nice();


            // Set z (color scale) domain based on the unique keys
            z.domain(keys);
        
            // Draw the bars
            g.append("g")
                .selectAll("g")
                .data(d3.stack().keys(keys)(dataset))
                .enter().append("g")
                .attr("fill", d => z(d.key))
                .selectAll("rect")
                .data(d => d)
                .enter().append("rect")
                .attr("x", d => x(d.data[attribute]))
                .attr("y", d => y(d[1]))
                .attr("height", d => y(d[0]) - y(d[1]))
                .attr("width", x.bandwidth());
        
            // Draw x-axis
            g.append("g")
                .attr("class", "axis")
                .attr("transform", `translate(0,${height})`)
                .call(d3.axisBottom(x));
        
            // Draw y-axis
            g.append("g")
                .attr("class", "axis")
                .call(d3.axisLeft(y).ticks(null, "s"))
                .append("text")
                .attr("x", 2)
                .attr("y", y(y.ticks().pop()) + 0.5)
                .attr("dy", "0.32em")
                .attr("fill", "#000")
                .attr("font-weight", "bold")
                .attr("text-anchor", "start")
                .text("Count");
        
            // Draw legend (optional)
            const legend = g.append("g")
                .attr("font-family", "sans-serif")
                .attr("font-size", 10)
                .attr("text-anchor", "end")
                .selectAll("g")
                .data(keys.slice().reverse())
                .enter().append("g")
                .attr("transform", (d, i) => `translate(0,${i * 20})`);
        
            legend.append("rect")
                .attr("x", width - 19)
                .attr("width", 19)
                .attr("height", 19)
                .attr("fill", z);
        
            legend.append("text")
                .attr("x", width - 24)
                .attr("y", 9.5)
                .attr("dy", "0.32em")
                .text(d => getGradeForCode(d));
            
        }
        
        // Common function to create a bar chart
        function createBarChart(targetId, attribute, customOrder, sportPyramidData, binnedCodeDict) {
            const { svg, g, x, y, z, width, height, margin } = setupChart(targetId);

            let uniqueBinnedCodes = [...new Set(sportPyramidData.map(item => item.binned_code))];
            let filteredBinnedCodeDict = binnedCodeDict.filter(entry => uniqueBinnedCodes.includes(entry.binned_code));

            const keys = filteredBinnedCodeDict.map(d => d.binned_code);

            sportPyramidData.forEach(d => {
                if (!d[attribute] && d[attribute] !== 0) {
                    d[attribute] = "Unknown";
                }
            });

            // Aggregate data using d3.group
            const groupedData = d3.group(sportPyramidData, d => d[attribute]);
            let dataset = Array.from(groupedData, ([key, values]) => {
                let counts = {};
                for (let v of values) {
                    if (counts[v.binned_code]) {
                        counts[v.binned_code]++;
                    } else {
                        counts[v.binned_code] = 1;
                    }
                }
                return {
                    [attribute]: key,
                    ...counts
                };
            });

            // If customOrder is provided, use it. Otherwise, default to dataset's attributes
            x.domain(customOrder ? customOrder.filter(order => dataset.map(d => d[attribute]).includes(order)) : dataset.map(d => d[attribute]));

            drawBarsAndAxes({ svg, g, x, y, z, width, height, margin, dataset, keys, attribute });
        }

        //Filter Data
        d3.select(characteristicsId).select("svg").remove();
        d3.select(lengthId).select("svg").remove();
        d3.select(styleId).select("svg").remove();

        // Apply time filter
        var timeFrame = d3.select("input[name='characteristics-time-filter']:checked").node().value;

        // Apply filters
        var filteredData = CommonFilters.filterByTime(inputData, timeFrame);

        //Characteristics
        createBarChart(characteristicsId, 'route_characteristic', null, filteredData, binnedCodeDict);
        //Length
        const customOrder = ['short', 'medium', 'long', 'multipitch', 'Unknown'];
        createBarChart(lengthId, 'length_category', customOrder, filteredData, binnedCodeDict);
        //Style
        createBarChart(styleId, 'route_style', null, filteredData, binnedCodeDict);

    }

    function determineData() {
        var discipline = d3.select("input[name='characteristics-discipline-filter']:checked").node().value;

        switch(discipline) {
            case 'sport':
                return sportPyramidData;
            case 'trad':
                return tradPyramidData;
            case 'boulder':
                return boulderPyramidData;
            default:
                console.error("Unknown discipline type");
                return [];
        }
    }

    function updatePerformanceVisualization() {
        var data = determineData();
        characterVizChart("#performance-characteristics", "#performance-length", "#performance-style", data, binnedCodeDict);
    }

    d3.selectAll("input[name='characteristics-discipline-filter']")
    .on('change.updateVisualization', updatePerformanceVisualization);

    d3.selectAll("input[name='characteristics-time-filter']")
        .on('change.updateVisualization', updatePerformanceVisualization);

    updatePerformanceVisualization();
});