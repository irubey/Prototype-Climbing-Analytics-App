document.addEventListener("DOMContentLoaded", function() {
   function pyramidVizChart(targetId, inputData, binnedCodeDict){

        // Helper Functions Global
        function createSVGChartContainer(targetId, margin, width, height) {
            return d3.select(targetId)
                .append("svg")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", `translate(${margin.left},${margin.top})`);
        }
        
        function createLinearScale(range) {
            return d3.scaleLinear().range(range);
        }
        
        function createBandScale(range, padding) {
            return d3.scaleBand().range(range).padding(padding);
        }

        function convertDictToObj(dict) {
            if (!Array.isArray(dict)) {
                console.error("The input is not an array:", dict);
                return {};
            }
            var obj = {};
            dict.forEach(function(d) {
                obj[d.binned_code] = d.binned_grade;
            });
            return obj;
        }
        
        
        //Helper Functions -- Grade Pyramids
        function getTrianglePath(side, count, binned_grade, binned_code, isFlashOnsight, width, x, y, joinedDataArray, maxBinnedCode) {
            if (count === 0 || count === null) {
                return null;
            }
        
            if (binned_code === maxBinnedCode && isFlashOnsight) {
                return null;
            }
        
            const xValue = x(count);
            const yValue = y(binned_grade);
            
            const x1 = side === 'left' 
                ? (width - xValue) / 2 - 1 
                : (width + xValue) / 2 + 1;
                    
            const y1 = yValue + y.bandwidth();
            
            const nextBinnedCode = parseInt(binned_code) + 1;
            const nextBinnedCodeData = joinedDataArray.find(d => d.binned_code == nextBinnedCode);
            
            let nextGradeCount;
            if (isFlashOnsight) {
                nextGradeCount = nextBinnedCodeData ? nextBinnedCodeData.flashOnsightCount : null;
            } else {
                nextGradeCount = nextBinnedCodeData ? nextBinnedCodeData.count : null;
            }
        
            if (nextGradeCount > count) {
                return null;
            }
            
            let x2;
            if (nextGradeCount !== null) {
                x2 = side === 'left' 
                    ? (width - x(nextGradeCount)) / 2 
                    : (width + x(nextGradeCount)) / 2;
            } else {
                x2 = side === 'left' 
                    ? x1 + (y1 - yValue) 
                    : x1 - (y1 - yValue);
            }
        
            if (binned_code == maxBinnedCode) {
                x2 = width / 2;
            } else {
                // 45-degree angle check for non-maxBinnedCode triangles
                if (Math.abs(x2 - x1) > (y1 - yValue)) {
                    x2 = side === 'left' 
                        ? x1 + (y1 - yValue) 
                        : x1 - (y1 - yValue);
                }
            }
            
            const y2 = isFlashOnsight ? yValue : yValue - 1;
            const x3 = x1;
            const y3 = y2;
            
            return `M ${x1} ${y1} L ${x2} ${y2} L ${x3} ${y3} Z`;
        }    
        
        function computeDataFrequencies(data) {
            var counts = {};
            data.forEach(function(d) {
                counts[d.binned_code] = (counts[d.binned_code] || 0) + 1;
            });
            return counts;
        }
        
        function createPyramidVisualization(targetId, inputData, binnedCodeDict) {
            d3.select(targetId).select("svg").remove();

            const margin = { top: 20, right: 20, bottom: 30, left: 80 };
            const width = 500 - margin.left - margin.right;
            const height = 300 - margin.top - margin.bottom;
        
            const svg = createSVGChartContainer(targetId, margin, width, height);
            const x = createLinearScale([0, width]);
            const y = createBandScale([height, 0],0);
        
            // Convert the binnedCodeDict to an object for easier lookup
            var binnedCodeObj = convertDictToObj(binnedCodeDict);

            // Apply time filter
            var timeFrame = d3.select("input[name='performance-pyramid-time-filter']:checked").node().value;
        
            // Apply filters
            var filteredData = CommonFilters.filterByTime(inputData, timeFrame);

            // Count the frequency of each binned_code in the filtered Data
            var counts = computeDataFrequencies(filteredData);
        
            // Convert the counts to an array of objects
            var data = [];
            for (var key in counts) {
            data.push({binned_code: parseInt(key), count: counts[key]});
            }

            // Sort the data by binned_code in ascending order
            data.sort(function(a, b) {
            return a.binned_code - b.binned_code;
            });

            // Find the min and max binned_code in the data
            var minCode = data[0].binned_code;
            var maxCode = data[data.length - 1].binned_code;

            // Create an array of all possible binned_codes between min and max
            var allCodes = [];
            for (var i = minCode; i <= maxCode; i++) {
            allCodes.push(i);
            }

            // Create an array of objects with binned_code and binned_grade for each possible code
            var allData = [];
            allCodes.forEach(function(code) {
            allData.push({binned_code: code, binned_grade: binnedCodeObj[code]});
            });

            // Join the data with the allData based on binned_code
            var joinedData = [];
            allData.forEach(function(d) {
            var found = false;
            data.forEach(function(e) {
                if (d.binned_code == e.binned_code) {
                joinedData.push({binned_code: d.binned_code, binned_grade: d.binned_grade, count: e.count});
                found = true;
                }
            });
            if (!found) {
                joinedData.push({binned_code: d.binned_code, binned_grade: d.binned_grade, count: null});
            }
            });


            //Count onsight and flash
            var flashOnsightCounts = {};
            filteredData.forEach(function(d) {
                if (d.lead_style === 'Flash' || d.lead_style === 'Onsight') {
                    flashOnsightCounts[d.binned_code] = (flashOnsightCounts[d.binned_code] || 0) + 1;
                }
            });


            // add new data to joined data
            joinedData.forEach(function(d) {
            d.flashOnsightCount = flashOnsightCounts[d.binned_code] || 0;
            });
        
            
            // Find the maximum count in the joined data
            var maxCount = d3.max(joinedData, function(d) { return d.count; });

            // Set the domain of the x scale to [0, maxCount]
            x.domain([0, maxCount]);

            // Set the domain of the y scale to the binned_grades in the joined data
            y.domain(joinedData.map(function(d) { return d.binned_grade; }));

            // Append a group element for each bar in the joined data
            var bars = svg.selectAll(".bar")
                .data(joinedData)
                .enter().append("g")
                .attr("class", "bar");

            // Append a rect element for each bar and set its attributes
            bars.append("rect")
                .attr("x", function(d) { return (width - x(d.count || 0)) / 2; }) // Use zero if the count is null
                .attr("y", function(d) { return y(d.binned_grade); })
                .attr("width", function(d) { return x(d.count || 0); }) // Use zero if the count is null
                .attr("height", y.bandwidth())
                .attr("fill", "steelblue"); // Set the fill color of the bars


            // add onsight and flash bars
            bars.append("rect")
                .attr("x", function(d) { return (width - x(d.flashOnsightCount)) / 2; })
                .attr("y", function(d) { return y(d.binned_grade); })
                .attr("width", function(d) { return x(d.flashOnsightCount); })
                .attr("height", y.bandwidth()) 
                .attr("fill", "orange");  // Choose a different color for these bars


            // Create triangles that form the pyramid structure
            // For flash/onsight counts:
            bars.append("path")
                .attr("d", function(d) { 
                    return getTrianglePath('left', d.flashOnsightCount, d.binned_grade, d.binned_code, true, width, x, y, joinedData, maxCode);
                })
                .attr("fill", "steelblue");

            bars.append("path")
                .attr("d", function(d) { 
                    return getTrianglePath('right', d.flashOnsightCount, d.binned_grade, d.binned_code, true, width, x, y, joinedData, maxCode);
                })
                .attr("fill", "steelblue");

            // For the main count:
            bars.append("path")
                .attr("d", function(d) { 
                    return getTrianglePath('left', d.count, d.binned_grade, d.binned_code, false, width, x, y, joinedData, maxCode);
                })
                .attr("fill", "white");

            bars.append("path")
                .attr("d", function(d) { 
                    return getTrianglePath('right', d.count, d.binned_grade, d.binned_code, false, width, x, y, joinedData, maxCode);
                })
                .attr("fill", "white");


            //Append dashed horizontal lines seperating horizontal bars
            svg.selectAll(".dashed-line")
                .data(joinedData)
                .enter().append("line")
                .attr("class", "dashed-line")
                .attr("x1", 0)
                .attr("x2", width)
                .attr("y1", function(d) { return y(d.binned_grade) + y.bandwidth(); })
                .attr("y2", function(d) { return y(d.binned_grade) + y.bandwidth(); })
                .attr("stroke", "Grey")  // Color of the dashed line
                .attr("stroke-dasharray", "3,3");  // Dashed pattern (5 pixels dash, 5 pixels gap)

                
            bars.append("text")
                .attr("x", width) 
                .attr("y", function(d) { return y(d.binned_grade) + y.bandwidth() * 0.4; })  // Adjust for centering
                .attr("font-size", "10px")
                .attr("text-anchor", "end")
                .text(function(d) { 
                    if(d.flashOnsightCount > 0) {  // Display only if count is greater than zero
                        return `First Go: ${d.flashOnsightCount}`; 
                    } else {
                        return "";
                    }
                });
            // Append text labels denoting binned_code total count
            bars.append("text")
                .attr("x", width)  // right edge of the chart
                .attr("y", function(d) { return y(d.binned_grade) + y.bandwidth() * 0.2; }) // adjusted position within the bar
                .attr("text-anchor", "end") // right-align the text
                .attr("font-size", "10px")
                .text(function(d) { return `Clean ascents: ${d.count || 0}`; });

            // Append a group element for the y axis and call the axis function
            svg.append("g")
                .attr("class", "y axis")
                .call(d3.axisLeft(y));
        
        }

        createPyramidVisualization(targetId,inputData,binnedCodeDict);
        
    }

    function determineData() {
        var discipline = d3.select("input[name='performance-pyramid-discipline-filter']:checked").node().value;

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
        pyramidVizChart('#performance-pyramid', data, binnedCodeDict);
    }

    d3.selectAll("input[name='performance-pyramid-discipline-filter']")
    .on('change.updateVisualization', updatePerformanceVisualization);

    d3.selectAll("input[name='performance-pyramid-time-filter']")
        .on('change.updateVisualization', updatePerformanceVisualization);

    updatePerformanceVisualization();
});
