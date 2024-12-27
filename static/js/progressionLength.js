document.addEventListener("DOMContentLoaded", function () {
  function progressionLengthChart(userTicksData, targetId) {
    const parseDate = d3.timeParse("%Y-%m-%d");

    function getColor(category, type) {
      const colors = {
        length: {
          short: "#3498DB", // Peter river blue
          medium: "#2ECC71", // Emerald green
          long: "#F1C40F", // Sunflower yellow
          multipitch: "#E74C3C", // Alizarin red
        },
      };

      return colors[type][category] || "#95A5A6"; // Default to neutral gray
    }

    function prepareData(userTicksData, mapFn) {
      const hasInvalidDates = userTicksData.some(
        (entry) =>
          !entry.tick_date ||
          (typeof entry.tick_date === "string" && entry.tick_date.trim() === "")
      );
      if (hasInvalidDates) {
        throw new Error(
          "userTicksData contains invalid data or null date values"
        );
      }

      // Filter out entries with null/undefined length_category
      userTicksData = userTicksData.filter(
        (d) =>
          d.length_category &&
          d.length_category !== "null" &&
          d.length_category !== "undefined"
      );

      // Calculate total sends and attempts per category
      const categoryStats = {};
      userTicksData.forEach((d) => {
        const category = d.length_category;
        if (!categoryStats[category]) {
          categoryStats[category] = {
            sends: 0,
            attempts: 0,
          };
        }

        // Calculate attempts and sends based on the rules
        if (d.length_category !== "multipitch") {
          if (d.send_bool) {
            categoryStats[category].attempts += d.pitches - 1 || 0;
            categoryStats[category].sends++;
          } else {
            categoryStats[category].attempts += d.pitches || 0;
          }
        } else {
          // Multipitch rules
          if (d.send_bool) {
            categoryStats[category].sends++;
          } else {
            categoryStats[category].attempts++;
          }
        }
      });

      return userTicksData.map((d) => ({
        date: parseDate(d.tick_date),
        category: d.length_category,
        pitches: d.pitches || 0,
        categoryStats: categoryStats[d.length_category],
      }));
    }

    function createChart(
      inputData,
      categoryField,
      categoryType,
      colorFunc,
      filterFunc,
      svgId
    ) {
      // Calculate dimensions based on container width
      const container = d3.select(svgId).node().getBoundingClientRect();
      const margin = { top: 20, right: 110, bottom: 60, left: 70 };
      const width = Math.min(container.width - margin.left - margin.right, 700);
      const height = width * 0.5;

      const svg = d3
        .select(svgId)
        .append("svg")
        .attr("width", "100%")
        .attr("height", height + margin.top + margin.bottom)
        .attr(
          "viewBox",
          `0 0 ${width + margin.left + margin.right} ${
            height + margin.top + margin.bottom
          }`
        )
        .attr("preserveAspectRatio", "xMidYMid meet")
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const xScale = d3.scaleTime().range([0, width]);
      const yScale = d3.scaleLinear().range([height, 0]);

      // Add grid lines first (in background)
      function makeGridlines() {
        return d3.axisLeft(yScale).ticks(5);
      }

      // Add the X gridlines
      svg
        .append("g")
        .attr("class", "grid")
        .attr("transform", `translate(0,${height})`)
        .style("stroke-dasharray", "3,3")
        .style("opacity", 0.1)
        .call(d3.axisBottom(xScale).ticks(12).tickSize(-height).tickFormat(""));

      // Add the Y gridlines
      svg
        .append("g")
        .attr("class", "grid")
        .style("stroke-dasharray", "3,3")
        .style("opacity", 0.1)
        .call(makeGridlines().tickSize(-width).tickFormat(""));

      const line = d3
        .line()
        .x((d) => xScale(d.date))
        .y((d) => yScale(d.totalPitches))
        .curve(d3.curveMonotoneX);

      const categories = [...new Set(inputData.map((d) => d[categoryField]))];
      let dataByCategory = {};

      // Process data by category
      categories.forEach((cat) => {
        let categoryData = inputData
          .filter((d) => d[categoryField] === cat)
          .sort((a, b) => new Date(a.date) - new Date(b.date));

        // Only process and add to dataByCategory if there's actual data
        if (categoryData.length > 0) {
          let totalPitches = 0;
          categoryData.forEach((d) => {
            totalPitches += d.pitches;
            d.totalPitches = totalPitches;
          });

          // Extend the last value to the current date
          const lastPoint = categoryData[categoryData.length - 1];
          const today = new Date();

          // Only add extension point if the last data point isn't already at the end
          if (lastPoint.date < today) {
            categoryData.push({
              ...lastPoint,
              date: today,
              totalPitches: lastPoint.totalPitches,
            });
          }

          dataByCategory[cat] = categoryData;
        }
      });

      const allData = Object.values(dataByCategory)
        .filter((data) => data.length > 0)
        .flat();

      // Only proceed if we have data
      if (allData.length === 0) return;

      // Set x domain from earliest data point to today
      const today = new Date();
      const earliestDate = d3.min(allData, (d) => new Date(d.date));
      xScale.domain([earliestDate, today]);
      yScale.domain([0, d3.max(allData, (d) => d.totalPitches)]);

      // Style the axes
      svg
        .append("g")
        .attr("class", "x-axis")
        .attr("transform", `translate(0,${height})`)
        .call(
          d3.axisBottom(xScale).ticks(6).tickFormat(d3.timeFormat("%b '%y"))
        )
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("dx", "-.8em")
        .attr("dy", ".15em")
        .attr("transform", "rotate(-45)")
        .style("font-size", "11px");

      svg
        .append("g")
        .attr("class", "y-axis")
        .call(d3.axisLeft(yScale).ticks(5))
        .selectAll("text")
        .style("font-size", "11px");

      // Add axis labels
      svg
        .append("text")
        .attr("class", "x-label")
        .attr("text-anchor", "middle")
        .attr("x", width / 2)
        .attr("y", height + margin.bottom - 5)
        .style("font-size", "12px")
        .text("Date");

      svg
        .append("text")
        .attr("class", "y-label")
        .attr("text-anchor", "middle")
        .attr("transform", "rotate(-90)")
        .attr("y", -margin.left + 20)
        .attr("x", -height / 2)
        .style("font-size", "12px")
        .text("Total Pitches");

      // Add tooltip div
      const tooltip = d3
        .select("body")
        .selectAll(".length-tooltip")
        .data([0])
        .join("div")
        .attr("class", "length-tooltip")
        .style("opacity", 0)
        .style("position", "absolute")
        .style("background-color", "rgba(255, 255, 255, 0.9)")
        .style("border", "1px solid #ddd")
        .style("border-radius", "4px")
        .style("padding", "8px")
        .style("pointer-events", "none")
        .style("font-size", "12px")
        .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
        .style("z-index", 1000);

      // Draw the lines with hover interaction
      categories.forEach((cat) => {
        svg
          .append("path")
          .datum(dataByCategory[cat])
          .attr("class", "line")
          .attr("d", line)
          .style("stroke", colorFunc(cat))
          .style("stroke-width", "2.5")
          .style("fill", "none")
          .style("opacity", 0.8)
          .on("mouseover", function (event) {
            const lastPoint =
              dataByCategory[cat][dataByCategory[cat].length - 1];
            const stats = lastPoint.categoryStats;
            const totalAttempts = stats.attempts + stats.sends;
            const sendRate =
              totalAttempts > 0
                ? ((stats.sends / totalAttempts) * 100).toFixed(1)
                : "0.0";

            tooltip
              .html(
                `
                <div style='font-weight: bold; margin-bottom: 4px;'>${cat}</div>
                <div style='color: ${colorFunc(cat)}'>
                  Send Rate: ${sendRate}%<br>
                  (${stats.sends} sends / ${totalAttempts} attempts)<br>
                  Total Pitches: ${lastPoint.totalPitches}
                </div>
              `
              )
              .style("left", event.pageX + 15 + "px")
              .style("top", event.pageY - 28 + "px")
              .style("opacity", 1);

            // Highlight the current line
            d3.select(this).style("stroke-width", "4").style("opacity", 1);
          })
          .on("mouseout", function () {
            tooltip.style("opacity", 0);
            d3.select(this).style("stroke-width", "2.5").style("opacity", 0.8);
          });
      });

      // Define the specific order of categories for the legend
      let orderedCategories = ["short", "medium", "long", "multipitch"];

      // Filter orderedCategories to only include categories that have data
      orderedCategories = orderedCategories.filter(
        (cat) => dataByCategory[cat] && dataByCategory[cat].length > 0
      );

      // Enhanced legend
      const legendSpace = 25; // Increased spacing
      const legend = svg
        .append("g")
        .attr("class", "legend")
        .attr("transform", `translate(${width + 10}, 5)`); // Moved legend to right side

      orderedCategories.forEach((cat, i) => {
        const legendItem = legend
          .append("g")
          .attr("transform", `translate(0,${i * legendSpace})`);

        // Legend color boxes
        legendItem
          .append("rect")
          .attr("width", 12)
          .attr("height", 12)
          .attr("rx", 2) // Rounded corners
          .style("fill", colorFunc(cat))
          .style("opacity", 0.8);

        // Legend text
        legendItem
          .append("text")
          .attr("x", 20)
          .attr("y", 9)
          .text(cat)
          .style("font-size", "12px")
          .style("font-weight", "500")
          .style("alignment-baseline", "middle");
      });
    }

    d3.select(targetId).select("svg").remove();

    var discipline = d3
      .select("input[name='length-cat-discipline-filter']:checked")
      .node().value;
    var timeFrame = d3
      .select("input[name='length-cat-time-filter']:checked")
      .node().value;

    // Apply filters
    var filteredData = CommonFilters.filterByDiscipline(
      userTicksData,
      discipline
    );
    filteredData = CommonFilters.filterByTime(filteredData, timeFrame);
    filteredData = prepareData(filteredData, (d) => ({
      date: parseDate(d.tick_date),
      category: d.length_category,
      pitches: d.pitches || 0,
    }));
    createChart(
      filteredData,
      "category",
      "length",
      (cat) => getColor(cat, "length"),
      (d) => true,
      "#length-cat"
    );
  }

  // Add event listeners to your filters
  d3.selectAll("input[name='length-cat-discipline-filter']").on(
    "change",
    function () {
      progressionLengthChart(userTicksData, "#length-cat");
    }
  );

  d3.selectAll("input[name='length-cat-time-filter']").on(
    "change",
    function () {
      progressionLengthChart(userTicksData, "#length-cat");
    }
  );

  progressionLengthChart(userTicksData, "#length-cat");
});
