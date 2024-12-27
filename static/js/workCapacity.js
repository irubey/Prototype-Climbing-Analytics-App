document.addEventListener("DOMContentLoaded", function () {
  function workCapacityChart(targetId, userTicksData) {
    // Utilities
    const parseDate = d3.timeParse("%Y-%m-%d");
    const formatDate = d3.timeFormat("%Y-%m-%d");

    // Data Calcs
    function transformData(data) {
      return data.map((d) => ({
        date: parseDate(d.tick_date),
        seasonCategory: d.season_category,
        routeName: d.route_name,
        length: d.length === 0 ? null : d.length,
        pitches: d.pitches,
        length_category: d.length_category,
        discipline: d.discipline,
      }));
    }

    function calculateAverageLength(data) {
      const averageLengthMap = new Map();

      data.forEach((d) => {
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
      // Default lengths based on route type
      const defaultLengths = {
        sport: 80, // Average sport route 80ft
        trad: 100, // Average trad route 100ft
        boulder: 10, // Average boulder 10ft
        multipitch_base: 80, // Base length for multipitch pitches
      };

      return data
        .map((d) => {
          const dateString = formatDate(d.date);
          if (d.length === 0 || isNaN(d.length)) {
            // Try to use daily average first
            const dailyAvg = averageLengthMap.get(dateString);
            if (dailyAvg) {
              d.length = dailyAvg;
            } else {
              // If no daily average, use default based on discipline and type
              if (d.length_category === "multipitch") {
                // For multipitch without length, use base length * pitches
                d.length = defaultLengths.multipitch_base * d.pitches;
              } else if (d.discipline === "sport") {
                d.length = defaultLengths.sport;
              } else if (d.discipline === "trad") {
                d.length = defaultLengths.trad;
              } else if (d.discipline === "boulder") {
                d.length = defaultLengths.boulder;
              }
            }
          }
          return d;
        })
        .filter((d) => d.length !== null && d.length !== undefined);
    }

    function calculateTotalVertical(data) {
      const verticalMap = new Map();

      data.forEach((d) => {
        // Calculate vertical feet based on route type and length availability
        if (d.length_category === "multipitch") {
          // For multipitch: if length exists, use it directly; otherwise it's already calculated as base * pitches
          d.vertical = d.length;
        } else {
          // For non-multipitch: multiply length by pitches (for repeat ascents)
          d.vertical = d.length * d.pitches;
        }

        // Count all pitches regardless of route type
        d.totalPitches = d.pitches;

        const dateString = formatDate(d.date);
        const mapKey = `${dateString}_${d.seasonCategory}`;

        if (!verticalMap.has(mapKey)) {
          verticalMap.set(mapKey, {
            total: d.vertical,
            pitches: d.totalPitches,
            seasonCategory: d.seasonCategory,
          });
        } else {
          const current = verticalMap.get(mapKey);
          current.total += d.vertical;
          current.pitches += d.totalPitches;
        }
      });

      const output = [];
      verticalMap.forEach((value, key) => {
        const [dateString, _] = key.split("_");
        const dateObj = parseDate(dateString);
        output.push({
          date: dateObj,
          totalVertical: value.total,
          totalPitches: value.pitches,
          seasonCategory: value.seasonCategory,
        });
      });

      return output;
    }

    //Chart setup and generation
    function setupChart(targetId) {
      // Calculate dimensions based on container width
      const container = d3.select(targetId).node().getBoundingClientRect();
      // Increase bottom margin for x-axis labels and left margin for y-axis
      const margin = { top: 20, right: 110, bottom: 100, left: 80 };
      // Limit max width and make it slightly smaller
      const width = Math.min(container.width - margin.left - margin.right, 700);
      // Use same height ratio as totalVert
      const height = width * 0.5;

      const svg = d3
        .select(targetId)
        .append("svg")
        .attr("width", "100%")
        .attr("height", height + margin.top + margin.bottom)
        .attr(
          "viewBox",
          `0 0 ${width + margin.left + margin.right} ${
            height + margin.top + margin.bottom
          }`
        )
        .attr("preserveAspectRatio", "xMidYMid meet");

      const g = svg
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const x = d3
        .scaleBand()
        .rangeRound([0, width])
        .paddingInner(0.05)
        .align(0.1);
      const y = d3.scaleLinear().rangeRound([height, 0]);

      return { svg, g, x, y, width, height, margin };
    }

    function generateBarChart(data, targetId) {
      // Compute average for each seasonCategory
      const averageData = Array.from(
        d3.rollup(
          data,
          (group) => ({
            seasonCategory: group[0].seasonCategory,
            averageVertical: d3.mean(group, (d) => d.totalVertical) || 0,
            averagePitches: d3.mean(group, (d) => d.totalPitches) || 0,
          }),
          (d) => d.seasonCategory
        ),
        ([_, entry]) => entry
      );

      const { svg, g, x, y, width, height, margin } = setupChart(targetId);

      // Define base seasonal colors
      const seasonColors = {
        Spring: "#89c97d",
        Summer: "#2e7d32",
        Fall: "#bf783b",
        Winter: "#78909c",
      };

      // Function to get color based on season
      const getSeasonColor = (seasonCategory) => {
        const season = seasonCategory
          ? seasonCategory.split(" ")[0].replace(",", "")
          : "";
        return seasonColors[season] || "#4caf50";
      };

      x.domain(averageData.map((d) => d.seasonCategory));
      y.domain([0, d3.max(averageData, (d) => d.averageVertical)]);

      // Calculate the overall averages
      const overallAverage = d3.mean(averageData, (d) => d.averageVertical);
      const overallPitches = d3.mean(averageData, (d) => d.averagePitches);

      // Add bars with seasonal colors
      g.selectAll(".bar")
        .data(averageData)
        .enter()
        .append("rect")
        .attr("class", "bar")
        .attr("x", (d) => x(d.seasonCategory))
        .attr("y", (d) => y(d.averageVertical))
        .attr("width", x.bandwidth())
        .attr("height", (d) => height - y(d.averageVertical))
        .style("fill", (d) => getSeasonColor(d.seasonCategory))
        .style("stroke", "none")
        .style("transition", "opacity 0.2s")
        .on("mouseover", function (event, d) {
          d3.select(this).style("opacity", 0.8);

          // Show tooltip with vertical feet only
          const season = d.seasonCategory.split(" ")[0].replace(",", "");
          const tooltip = g
            .append("text")
            .attr("class", "bar-tooltip")
            .attr("x", x(d.seasonCategory) + x.bandwidth() / 2)
            .attr("y", y(d.averageVertical) - 5)
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .text(`${season}: ${Math.round(d.averageVertical)} ft/day`);
        })
        .on("mouseout", function () {
          d3.select(this).style("opacity", 1);
          g.selectAll(".bar-tooltip").remove();
        });

      // Add average line
      g.append("line")
        .attr("class", "average-line")
        .attr("x1", 0)
        .attr("x2", width)
        .attr("y1", y(overallAverage))
        .attr("y2", y(overallAverage))
        .style("stroke", "#2d3250")
        .style("stroke-dasharray", "4,4")
        .style("stroke-width", 1.5);

      // Add average label with vertical feet only
      g.append("text")
        .attr("class", "average-label")
        .attr("x", width + 5)
        .attr("y", y(overallAverage))
        .attr("dy", "0.32em")
        .attr("font-size", "11px")
        .attr("font-weight", "600")
        .attr("fill", "#2d3250")
        .text(`Average: ${Math.round(overallAverage)} ft/day`);

      // Add seasonal legend
      const legendData = [
        { key: "Spring", label: "Spring" },
        { key: "Summer", label: "Summer" },
        { key: "Fall", label: "Fall" },
        { key: "Winter", label: "Winter" },
      ];

      const legend = g
        .append("g")
        .attr("transform", `translate(${width + 5}, 10)`);

      legendData.forEach((item, idx) => {
        const legendRow = legend
          .append("g")
          .attr("transform", `translate(0, ${idx * 20})`);

        legendRow
          .append("rect")
          .attr("width", 10)
          .attr("height", 10)
          .attr("fill", seasonColors[item.key]);

        legendRow
          .append("text")
          .attr("x", 15)
          .attr("y", 9)
          .style("font-size", "11px")
          .text(item.label);
      });

      // Update axis rendering
      // X Axis
      g.append("g")
        .attr("transform", `translate(0, ${height})`)
        .call(d3.axisBottom(x).tickSizeOuter(0))
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("dx", "-.8em")
        .attr("dy", ".15em")
        .attr("transform", "rotate(-65)")
        .style("font-size", "11px"); // Make text slightly smaller

      // Y Axis with formatted ticks
      const yAxis = g.append("g").call(
        d3
          .axisLeft(y)
          .ticks(6) // Limit number of ticks
          .tickFormat((d) => {
            if (d >= 1000) {
              return d / 1000 + "k";
            }
            return d;
          })
      );

      // Y axis label
      yAxis
        .append("text")
        .attr("transform", "rotate(-90)")
        .attr("y", -60) // Adjust position
        .attr("x", -(height / 2))
        .attr("dy", "0.71em")
        .attr("text-anchor", "middle")
        .attr("fill", "black")
        .style("font-size", "12px")
        .text("Average Daily Vertical Feet");
    }

    // Main Function
    function generateAverageVerticalChart(userTicksData, targetId) {
      d3.select(targetId).select("svg").remove();

      var discipline = d3
        .select("input[name='work-capacity-discipline-filter']:checked")
        .node().value;
      var timeFrame = d3
        .select("input[name='work-capacity-time-filter']:checked")
        .node().value;

      // Apply filters
      var filteredData;
      if (discipline === "routes") {
        // Combine sport and trad
        filteredData = userTicksData.filter(
          (d) => d.discipline === "sport" || d.discipline === "trad"
        );
      } else {
        // Boulder filter remains the same
        filteredData = userTicksData.filter((d) => d.discipline === discipline);
      }

      // Apply time filter
      filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

      const transformedData = transformData(filteredData);
      const averageLengthMap = calculateAverageLength(transformedData);
      const updatedData = calculateDailyVertical(
        transformedData,
        averageLengthMap
      );
      const output = calculateTotalVertical(updatedData);

      generateBarChart(output, targetId);
    }

    generateAverageVerticalChart(userTicksData, targetId);
  }

  // Add event listeners to your filters
  d3.selectAll("input[name='work-capacity-discipline-filter']").on(
    "change",
    function () {
      workCapacityChart("#work-capacity", userTicksData);
    }
  );

  d3.selectAll("input[name='work-capacity-time-filter']").on(
    "change",
    function () {
      workCapacityChart("#work-capacity", userTicksData);
    }
  );

  workCapacityChart("#work-capacity", userTicksData);
});
