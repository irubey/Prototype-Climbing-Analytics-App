document.addEventListener("DOMContentLoaded", function () {
  function attemptsVizChart(targetId, inputData, binnedCodeDict) {
    // Helper Functions Global
    function createSVGChartContainer(targetId, margin, width, height) {
      return d3
        .select(targetId)
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
      var obj = {};
      dict.forEach(function (d) {
        obj[d.binned_code] = d.binned_grade;
      });
      return obj;
    }

    // Helper Functions -- Attempts Funnel
    function convertArrayToDict(array) {
      const dict = {};
      array.forEach((entry) => {
        dict[entry.binned_code] = entry.binned_grade;
      });
      return dict;
    }

    function attemptsTrianglePath(
      side,
      average,
      binned_grade,
      binned_code,
      width,
      x,
      y,
      dataArray,
      minBinnedCode
    ) {
      if (average === 0 || average === null) {
        return null;
      }

      const xValue = x(average);
      let yValue = y(binned_grade) + 1; // Downward shift
      const yBase = yValue + y.bandwidth();

      const intBinnedCode = parseInt(binned_code, 10);
      const previousBinnedCode = intBinnedCode - 1;
      const intMinBinnedCode = parseInt(minBinnedCode, 10);
      const previousBinnedCodeData = dataArray.find(
        (d) => d.binned_code == previousBinnedCode
      );
      const previousGradeAverage = previousBinnedCodeData
        ? previousBinnedCodeData.average
        : 0;
      const xPrevValue = x(previousGradeAverage);

      // Condition: If the average of the next lowest binned_code is higher than the current average, return null
      if (previousGradeAverage > average) {
        return null;
      }

      let xStart, xEnd, xTurn, path;

      if (side === "left") {
        xStart = (width - xValue) / 2 - 1; // Outward shift
        xEnd = (width - xPrevValue) / 2 - 1; // Outward shift
        xTurn = Math.min(xStart + y.bandwidth(), xEnd);
      } else {
        xStart = (width + xValue) / 2 + 1; // Outward shift
        xEnd = (width + xPrevValue) / 2 + 1; // Outward shift
        xTurn = Math.max(xStart - y.bandwidth(), xEnd);
      }

      if (intBinnedCode === intMinBinnedCode) {
        if (side === "left") {
          const midPoint = xStart + xValue / 2 - 1; // Outward shift
          path = `
                        M ${xStart} ${yValue}
                        L ${xStart} ${yBase}
                        L ${midPoint} ${yBase}
                        Z
                    `;
        } else {
          // Handle the 'right' side
          const midPoint = xStart - xValue / 2 + 1; // Outward shift
          path = `
                        M ${xStart} ${yValue}
                        L ${xStart} ${yBase}
                        L ${midPoint} ${yBase}
                        Z
                    `;
        }
      } else {
        path = `
                    M ${xStart} ${yValue}
                    L ${xStart} ${yBase}
                    L ${xTurn} ${yBase}
                    Z
                `;
      }

      return path.trim();
    }

    function computeDataAverages(data) {
      var groupedData = {};
      data.forEach((d) => {
        if (!groupedData[d.binned_code]) {
          groupedData[d.binned_code] = { total: 0, count: 0 };
        }
        groupedData[d.binned_code].total += d.num_attempts;
        groupedData[d.binned_code].count += 1;
      });

      var minCode = Math.min(...data.map((d) => d.binned_code));
      var maxCode = Math.max(...data.map((d) => d.binned_code));
      var fullRange = Array.from(
        { length: maxCode - minCode + 1 },
        (_, i) => i + minCode
      );

      var averages = fullRange.map((code) => {
        return {
          key: code,
          value: groupedData[code]
            ? groupedData[code].total / groupedData[code].count
            : 0,
        };
      });
      return { averages, minCode, maxCode };
    }

    function createAttemptsVisualization(targetId, inputData, binnedCodeDict) {
      d3.select(targetId).select("svg").remove();

      const margin = { top: 20, right: 20, bottom: 30, left: 80 };
      const width = 500 - margin.left - margin.right;
      const height = 300 - margin.top - margin.bottom;

      const svg = createSVGChartContainer(targetId, margin, width, height);
      const x = createLinearScale([0, width]);
      const y = createBandScale([height, 0], 0);

      // Convert the binnedCodeDict to an object for easier lookup
      const binnedCodeLookup = convertArrayToDict(binnedCodeDict);
      var binnedCodeObj = convertDictToObj(binnedCodeDict);

      // Apply time filter
      var timeFrame = d3
        .select("input[name='performance-pyramid-time-filter']:checked")
        .node().value;

      // Apply filters
      var filteredData = CommonFilters.filterByTime(inputData, timeFrame);

      var { averages, minCode, maxCode } = computeDataAverages(filteredData);

      // Create an array of objects with binned_code and binned_grade for each possible code
      var allData = averages.map(function (avg) {
        return {
          binned_code: avg.key,
          binned_grade: binnedCodeObj[avg.key],
          average: avg.value,
        };
      });

      allData.sort((a, b) => a.binned_code - b.binned_code);

      //Set up the Domains
      x.domain([
        0,
        d3.max(allData, function (d) {
          return d.average;
        }),
      ]);
      y.domain(
        allData.map(function (d) {
          return binnedCodeLookup[d.binned_code] || d.binned_code;
        })
      ).padding(0);

      // Append a group element for each bar in the joined data
      var bars = svg
        .selectAll(".bar")
        .data(allData)
        .enter()
        .append("g")
        .attr("class", "bar");

      // Append a rect element for each bar and set its attributes
      bars
        .append("rect")
        .attr("x", function (d) {
          return (width - x(d.average || 0)) / 2;
        })
        .attr("y", function (d) {
          return y(binnedCodeLookup[d.binned_code] || d.binned_code);
        })
        .attr("width", function (d) {
          return x(d.average || 0);
        })
        .attr("height", y.bandwidth())
        .attr("fill", "steelblue");

      // Create triangles that form the pyramid structure
      bars
        .append("path")
        .attr("d", function (d) {
          return attemptsTrianglePath(
            "left",
            d.average,
            d.binned_grade,
            d.binned_code,
            width,
            x,
            y,
            allData,
            minCode
          );
        })
        .attr("fill", "white");

      bars
        .append("path")
        .attr("d", function (d) {
          return attemptsTrianglePath(
            "right",
            d.average,
            d.binned_grade,
            d.binned_code,
            width,
            x,
            y,
            allData,
            minCode
          );
        })
        .attr("fill", "white");

      svg.append("g").attr("class", "y axis").call(d3.axisLeft(y));

      // Append text labels denoting binned_code total count
      bars
        .append("text")
        .attr("x", width)
        .attr("y", function (d) {
          return (
            y(binnedCodeLookup[d.binned_code] || d.binned_code) +
            y.bandwidth() * 0.8
          );
        })
        .attr("text-anchor", "end")
        .attr("font-size", "10px")
        .text(function (d) {
          return `Avg Attempts per Send: ${d.average.toFixed(2) || 0}`;
        });

      svg
        .selectAll(".dashed-line")
        .data(allData)
        .enter()
        .append("line")
        .attr("class", "dashed-line")
        .attr("x1", 0)
        .attr("x2", width)
        .attr("y1", function (d) {
          const binnedGrade = binnedCodeLookup[d.binned_code];
          return y(binnedGrade) + y.bandwidth();
        })
        .attr("y2", function (d) {
          const binnedGrade = binnedCodeLookup[d.binned_code];
          return y(binnedGrade) + y.bandwidth();
        })
        .attr("stroke", "Grey") // Color of the dashed line
        .attr("stroke-dasharray", "3,3"); // Dashed pattern (5 pixels dash, 5 pixels gap)
    }

    createAttemptsVisualization(targetId, inputData, binnedCodeDict);
  }

  function determineData() {
    var discipline = d3
      .select("input[name='performance-pyramid-discipline-filter']:checked")
      .node().value;

    switch (discipline) {
      case "sport":
        return sportPyramidData;
      case "trad":
        return tradPyramidData;
      case "boulder":
        return boulderPyramidData;
      default:
        console.error("Unknown discipline type");
        return [];
    }
  }

  function updateAttemptsVisualization() {
    var data = determineData();
    attemptsVizChart("#attempts-funnel", data, binnedCodeDict);
  }

  // Add event listeners to your filters
  d3.selectAll("input[name='performance-pyramid-discipline-filter']").on(
    "change",
    updateAttemptsVisualization
  );
  d3.selectAll("input[name='performance-pyramid-time-filter']").on(
    "change",
    updateAttemptsVisualization
  );

  updateAttemptsVisualization();
});
