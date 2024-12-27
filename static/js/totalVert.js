document.addEventListener("DOMContentLoaded", function () {
  function totalVertChart(targetId, userTicksData) {
    //rendering functions
    const formatDate = d3.timeFormat("%Y-%m-%d");
    const parseDate = d3.timeParse("%Y-%m-%d");

    function transformData(data) {
      return data
        .filter((d) => !isNaN(d.pitches) || d.length_category === "multipitch")
        .map((d) => ({
          date: parseDate(d.tick_date),
          seasonCategory: d.season_category.slice(0, -6),
          routeName: d.route_name,
          length: d.length === 0 ? null : d.length,
          pitches: d.length_category === "multipitch" ? 1 : d.pitches,
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
      return data
        .map((d) => {
          const dateString = formatDate(d.date);
          if (d.length === 0 || isNaN(d.length)) {
            d.length = averageLengthMap.get(dateString);
          }
          return d;
        })
        .filter((d) => d.length !== null && d.length !== undefined);
    }

    function calculateTotalVertical(data) {
      // First calculate daily averages for non-multipitch routes
      const dailyAverages = new Map();
      data.forEach((d) => {
        if (d.length_category !== "multipitch" && d.length) {
          const dateString = formatDate(d.date);
          if (!dailyAverages.has(dateString)) {
            dailyAverages.set(dateString, { sum: d.length, count: 1 });
          } else {
            const entry = dailyAverages.get(dateString);
            entry.sum += d.length;
            entry.count++;
          }
        }
      });

      // Convert sums to averages
      dailyAverages.forEach((value, key) => {
        dailyAverages.set(key, value.sum / value.count);
      });

      const verticalMap = new Map();
      data.forEach((d) => {
        const dateString = formatDate(d.date);
        let vertical;

        if (d.length_category === "multipitch") {
          // For multipitch, use total length regardless of pitches
          vertical = d.length;
        } else {
          // For single pitch routes
          if (d.length) {
            // If length is available, use length * pitches
            vertical = d.length * d.pitches;
          } else {
            // If no length, try daily average
            const dailyAvg = dailyAverages.get(dateString);
            if (dailyAvg) {
              vertical = dailyAvg * d.pitches;
            } else {
              // Default to 60ft * pitches if no other data available
              vertical = 60 * d.pitches;
            }
          }
        }

        const mapKey = `${dateString}_${d.seasonCategory}`;
        if (!verticalMap.has(mapKey)) {
          verticalMap.set(mapKey, {
            total: vertical,
            seasonCategory: d.seasonCategory,
          });
        } else {
          const current = verticalMap.get(mapKey);
          current.total += vertical;
        }
      });

      // Convert the map to the desired output format
      const output = [];
      verticalMap.forEach((value, key) => {
        const [dateString, _] = key.split("_");
        const dateObj = parseDate(dateString);
        output.push({
          date: dateObj,
          totalVertical: value.total,
          seasonCategory: value.seasonCategory,
        });
      });

      return output;
    }

    function calcRunningTotalVertical(data) {
      // Sort the data by date
      data.sort((a, b) => a.date - b.date);

      let accumulator = 0;
      const runningTotalVertical = data.map((d) => {
        accumulator += d.totalVertical;
        return {
          date: d.date,
          runningTotalVertical: accumulator,
          seasonCategory: d.seasonCategory,
        };
      });

      return runningTotalVertical;
    }

    function setupChart(targetId) {
      // Calculate dimensions based on container width
      const container = d3.select(targetId).node().getBoundingClientRect();
      const margin = { top: 20, right: 110, bottom: 60, left: 60 };
      // Limit max width and make it slightly smaller
      const width = Math.min(container.width - margin.left - margin.right, 700);
      // Reduce height ratio for a more compact look
      const height = width * 0.5; // Changed from 0.7 to 0.5 for a wider, shorter chart

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

      const color = d3.scaleOrdinal().range(d3.schemeSet2);

      const x = d3.scaleTime().range([0, width]);
      const y = d3.scaleLinear().rangeRound([height, 0]);
      const z = color;

      // Define milestones
      const milestones = [
        { height: 1454, name: "Empire State Building" },
        { height: 1776, name: "One World Trade Center" },
        { height: 2640, name: "Half Mile" },
        { height: 2717, name: "Burj Khalifa" },
        { height: 4737, name: "Half Dome" },
        { height: 5280, name: "One Mile" },
        { height: 7569, name: "El Capitan" },
        { height: 10000, name: "10,000 ft" },
        { height: 14505, name: "Mt. Whitney" },
        { height: 15781, name: "Mont Blanc" },
        { height: 20310, name: "Denali" },
        { height: 26400, name: "5 Miles" },
        { height: 29029, name: "Mt. Everest" },
        { height: 35000, name: "Commercial Aircraft Cruising" },
        { height: 52800, name: "10 Miles" },
        { height: 62000, name: "Edge of Mesosphere" },
        { height: 100000, name: "Kármán Line (Space)" },
        { height: 158400, name: "30 Miles" },
        { height: 264000, name: "50 Miles" },
        { height: 328084, name: "ISS Orbit" },
        { height: 500000, name: "500,000 ft" },
      ];

      return { svg, g, x, y, z, width, height, margin, milestones };
    }

    function generateLineChart(inputArray, targetId) {
      var { svg, g, x, y, z, width, height, margin, milestones } =
        setupChart(targetId);

      // Add tooltip div
      const tooltip = d3
        .select("body")
        .append("div")
        .attr("class", "milestone-tooltip")
        .style("opacity", 0)
        .style("position", "absolute")
        .style("background-color", "white")
        .style("border", "1px solid #ddd")
        .style("border-radius", "4px")
        .style("padding", "8px")
        .style("pointer-events", "none")
        .style("font-size", "12px")
        .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)");

      inputArray.forEach((d) => {
        d.date = parseDate(formatDate(new Date(d.date)));
      });

      inputArray.sort((a, b) => a.date - b.date);

      // Get max vertical achieved and next milestone
      const maxVertical = d3.max(inputArray, (d) => d.runningTotalVertical);
      const nextMilestoneHeight =
        milestones.find((m) => m.height > maxVertical)?.height || maxVertical;

      // Find achievement dates and locations for milestones
      const milestoneAchievements = milestones.map((milestone) => {
        const achievementTick = inputArray.find(
          (tick) => tick.runningTotalVertical >= milestone.height
        );
        return {
          ...milestone,
          achieved: achievementTick ? true : false,
          achievedDate: achievementTick?.date,
          location: achievementTick?.location,
        };
      });

      x.domain([inputArray[0].date, inputArray[inputArray.length - 1].date]);
      y.domain([0, nextMilestoneHeight]);

      // Format y-axis ticks to be more readable
      const yAxis = d3.axisLeft(y).tickFormat((d) => {
        if (d >= 1000) {
          return d / 1000 + "k";
        }
        return d;
      });

      const line = d3
        .line()
        .x((d) => x(d.date))
        .y((d) => y(d.runningTotalVertical))
        .curve(d3.curveMonotoneX);

      // Add milestone reference lines
      const milestoneGroup = g.append("g").attr("class", "viz-milestone-lines");

      // Find next unachieved milestone
      const relevantMilestones = milestoneAchievements.filter(
        (m) =>
          m.height <= maxVertical ||
          m.height === milestones.find((m) => m.height > maxVertical)?.height
      );

      // Select key milestones that won't overlap
      const heightThreshold = height * 0.15; // 15% of chart height as minimum spacing
      const keyMilestones = [];
      let lastSelectedHeight = -Infinity;

      // Key heights we definitely want to show (in feet)
      const priorityHeights = [5280, 29029, 100000]; // One Mile, Everest, Space

      relevantMilestones.forEach((milestone) => {
        if (milestone.height <= y.domain()[1]) {
          const pixelDistance = Math.abs(
            y(milestone.height) - y(lastSelectedHeight)
          );
          const isPriorityMilestone = priorityHeights.includes(
            milestone.height
          );

          // Include if it's a priority milestone or if there's enough space
          if (isPriorityMilestone || pixelDistance > heightThreshold) {
            keyMilestones.push(milestone);
            lastSelectedHeight = milestone.height;
          }
        }
      });

      // Render all milestones, but only show key ones by default
      relevantMilestones.forEach((milestone) => {
        if (milestone.height <= y.domain()[1]) {
          const isKeyMilestone = keyMilestones.includes(milestone);

          const milestoneGroup = g
            .append("g")
            .attr("class", "viz-milestone")
            .classed("viz-future-milestone", milestone.height > maxVertical);

          // Add dashed reference line
          milestoneGroup
            .append("line")
            .attr("x1", 0)
            .attr("x2", width)
            .attr("y1", y(milestone.height))
            .attr("y2", y(milestone.height))
            .attr("stroke", milestone.height > maxVertical ? "#4caf50" : "#999")
            .attr("stroke-dasharray", "2,2")
            .attr("stroke-width", milestone.height > maxVertical ? 2 : 1)
            .style("opacity", milestone.height > maxVertical ? 0.8 : 0.5);

          // Add milestone label
          const labelGroup = milestoneGroup
            .append("g")
            .attr("class", "viz-milestone-label");

          // Format height for label
          const formattedHeight =
            milestone.height >= 1000
              ? `${(milestone.height / 1000).toFixed(1)}k`
              : milestone.height;

          // Add label text
          labelGroup
            .append("text")
            .attr("x", width + 5)
            .attr("y", y(milestone.height))
            .attr("dy", "0.32em")
            .attr("font-size", "10px")
            .attr("fill", milestone.height > maxVertical ? "#4caf50" : "#666")
            .style("opacity", isKeyMilestone ? 1 : 0) // Only show key milestones by default
            .text(`${milestone.name} (${formattedHeight}ft)`);

          // Add hover target
          milestoneGroup
            .append("rect")
            .attr("x", 0)
            .attr("y", y(milestone.height) - 5)
            .attr("width", width)
            .attr("height", 10)
            .attr("fill", "transparent")
            .style("cursor", "pointer")
            .on("mouseover", function (event) {
              // Show label for this milestone
              labelGroup.select("text").style("opacity", 1);

              tooltip.transition().duration(200).style("opacity", 0.9);

              let tooltipContent = `<strong>${milestone.name}</strong><br/>`;
              tooltipContent += `Height: ${milestone.height.toLocaleString()} ft<br/>`;

              if (milestone.achieved) {
                tooltipContent += `Achieved: ${d3.timeFormat("%B %d, %Y")(
                  milestone.achievedDate
                )}<br/>`;
                tooltipContent += milestone.location
                  ? `Location: ${milestone.location}`
                  : "";
              } else {
                tooltipContent += `<em>Not yet achieved</em>`;
              }

              tooltip
                .html(tooltipContent)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px");
            })
            .on("mouseout", function () {
              // Hide label if not a key milestone
              if (!isKeyMilestone) {
                labelGroup.select("text").style("opacity", 0);
              }
              tooltip.transition().duration(500).style("opacity", 0);
            });
        }
      });

      // Add the main line path
      g.append("path")
        .datum(inputArray)
        .attr("fill", "none")
        .attr("stroke", "black")
        .attr("stroke-width", 1.5)
        .attr("d", line);

      // Add current total callout
      const lastDataPoint = inputArray[inputArray.length - 1];
      const currentTotal = g
        .append("g")
        .attr("class", "current-total-label")
        .attr(
          "transform",
          `translate(${width + 5}, ${y(lastDataPoint.runningTotalVertical)})`
        );

      // Format current total
      const formattedTotal =
        lastDataPoint.runningTotalVertical >= 1000
          ? `${(lastDataPoint.runningTotalVertical / 1000).toFixed(1)}k`
          : lastDataPoint.runningTotalVertical;

      currentTotal
        .append("text")
        .attr("dy", "0.32em")
        .attr("font-size", "11px")
        .attr("font-weight", "600")
        .attr("fill", "#2d3250")
        .text(`Current Total: ${formattedTotal}ft`);

      // X Axis
      g.append("g")
        .attr("class", "viz-axis viz-x-axis")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b '%y")))
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("dx", "-.8em")
        .attr("dy", ".15em")
        .attr("transform", "rotate(-45)")
        .style("font-size", "11px");

      // Add light grid lines for x-axis
      g.append("g")
        .attr("class", "viz-grid")
        .attr("transform", `translate(0,${height})`)
        .style("stroke-dasharray", "3,3")
        .style("opacity", 0.1)
        .call(d3.axisBottom(x).ticks(12).tickSize(-height).tickFormat(""));

      // Y-Axis
      g.append("g").attr("class", "viz-axis viz-y-axis").call(d3.axisLeft(y));
    }

    d3.select(targetId).select("svg").remove();

    var discipline = d3
      .select("input[name='total-vert-discipline-filter']:checked")
      .node().value;
    var timeFrame = d3
      .select("input[name='total-vert-time-filter']:checked")
      .node().value;

    // Apply filters
    var filteredData = CommonFilters.filterByDiscipline(
      userTicksData,
      discipline
    );
    filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

    const transformedData = transformData(filteredData);
    const averageLengthMap = calculateAverageLength(transformedData);
    const updatedData = calculateDailyVertical(
      transformedData,
      averageLengthMap
    );
    const output = calculateTotalVertical(updatedData);
    const runningTotalVertical = calcRunningTotalVertical(output);

    generateLineChart(runningTotalVertical, targetId);
  }
  // Add event listeners to your filters
  d3.selectAll("input[name='total-vert-discipline-filter']").on(
    "change",
    function () {
      totalVertChart("#total-vert", userTicksData);
    }
  );

  d3.selectAll("input[name='total-vert-time-filter']").on(
    "change",
    function () {
      totalVertChart("#total-vert", userTicksData);
    }
  );

  totalVertChart("#total-vert", userTicksData);
});
