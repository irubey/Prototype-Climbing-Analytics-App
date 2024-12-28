document.addEventListener("DOMContentLoaded", function () {
  function characterVizChart(targetId, inputData, binnedCodeDict) {
    //Setup
    function getGradeForCode(binnedCode) {
      const entry = binnedCodeDict.find(
        (item) => item.binned_code === binnedCode
      );
      return entry ? entry.binned_grade : binnedCode;
    }

    function setupChart(targetId) {
      // Calculate dimensions based on container width
      const container = d3.select(targetId).node().getBoundingClientRect();
      const margin = { top: 40, right: 120, bottom: 80, left: 60 };
      const width = Math.min(container.width - margin.left - margin.right, 900);
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

      // Use a more distinct color palette
      const color = d3.scaleOrdinal().range([
        "#DB784D", // Terracotta (Fall) for highest grade
        "#F3B562", // Muted Gold (Summer)
        "#7CB9A8", // Sage Green (Spring)
        "#5B8BA0", // Dusty Blue (Winter) for lowest grade
      ]);

      const x = d3
        .scaleBand()
        .rangeRound([0, width])
        .paddingInner(0.05)
        .align(0.1);

      const y = d3.scaleLinear().rangeRound([height, 0]);
      const z = color;

      return { svg, g, x, y, z, width, height, margin };
    }

    function processData(data) {
      // Process data for all three categories
      const energyData = processCategory(data, "route_characteristic", [
        "Power",
        "Power Endurance",
        "Endurance",
      ]);
      const lengthData = processCategory(data, "length_category", [
        "short",
        "medium",
        "long",
        "multipitch",
      ]);
      const angleData = processCategory(data, "route_style", [
        "Slab",
        "Vertical",
        "Overhang",
        "Roof",
      ]);

      // Combine all data with group labels
      return [
        { group: "Energy System", data: energyData },
        { group: "Length", data: lengthData },
        { group: "Angle", data: angleData },
      ];
    }

    function processCategory(data, attribute, validValues) {
      const groupedData = d3.group(data, (d) => d[attribute] || "Unknown");
      return Array.from(groupedData, ([key, values]) => {
        const counts = {};
        const routesByGrade = {};

        // Initialize counts for all possible keys to 0
        keys.forEach((k) => {
          counts[k] = 0;
        });

        values.forEach((v) => {
          if (v.binned_code) {
            // Make sure binned_code exists
            counts[v.binned_code] = (counts[v.binned_code] || 0) + 1;
            if (!routesByGrade[v.binned_code]) {
              routesByGrade[v.binned_code] = [];
            }
            routesByGrade[v.binned_code].push({
              name: v.route_name,
              date: v.tick_date,
              grade: v.route_grade,
              location: v.location,
              attempts: v.num_attempts,
            });
          }
        });

        return {
          category: key,
          ...counts,
          routesByGrade,
          total: values.length,
        };
      })
        .filter((d) => validValues.includes(d.category))
        .sort((a, b) => b.total - a.total);
    }

    function createTooltip() {
      return d3
        .select("body")
        .append("div")
        .attr("class", "d3-tooltip")
        .style("position", "absolute")
        .style("visibility", "hidden")
        .style("background-color", "white")
        .style("border", "1px solid #ddd")
        .style("border-radius", "4px")
        .style("padding", "10px")
        .style("font-size", "12px")
        .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
        .style("max-width", "300px")
        .style("max-height", "400px")
        .style("overflow-y", "auto")
        .style("z-index", "1000");
    }

    function positionTooltip(event, tooltip) {
      const tooltipNode = tooltip.node();
      const tooltipRect = tooltipNode.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Default positions (10px offset from cursor)
      let left = event.pageX + 10;
      let top = event.pageY - 10;

      // Check right edge
      if (left + tooltipRect.width > viewportWidth - 10) {
        left = event.pageX - tooltipRect.width - 10;
      }

      // Check bottom edge
      if (top + tooltipRect.height > viewportHeight - 10) {
        top = event.pageY - tooltipRect.height - 10;
      }

      // Check top edge
      if (top < 10) {
        top = 10;
      }

      // Check left edge
      if (left < 10) {
        left = 10;
      }

      return { left, top };
    }

    function showTooltip(event, d, tooltip, gradeKey, data, isPinned = false) {
      const routes = (data.routesByGrade[gradeKey] || []).sort(
        (a, b) => new Date(b.date) - new Date(a.date)
      );
      const total = routes.length;

      let tooltipContent = `
        <div style="margin-bottom: 5px;">
          <strong>${getGradeForCode(gradeKey)} ${data.category}</strong>
          ${
            isPinned
              ? '<span style="float: right; cursor: pointer; color: #666;" class="close-btn">×</span>'
              : '<span style="float: right; font-size: 11px; color: #666;">Click to pin</span>'
          }
        </div>
        <div style="margin-bottom: 8px;">
          Total Pitches: ${total}
        </div>
        <div style="border-top: 1px solid #eee; padding-top: 5px;">
          <strong>Routes:</strong>
          ${routes
            .map(
              (route) => `
            <div style="margin-top: 3px; padding: 3px 0;">
              <div><strong>${route.name}</strong> ${route.grade}</div>
              <div style="font-size: 11px; color: #666;">
                ${route.location} • ${
                route.attempts === 1
                  ? "Flash/Onsight"
                  : `${route.attempts} attempts`
              } • ${new Date(route.date).toLocaleDateString()}
              </div>
            </div>
          `
            )
            .join("")}
        </div>
      `;

      tooltip.style("visibility", "visible").html(tooltipContent);

      if (isPinned) {
        tooltip.select(".close-btn").on("click", function () {
          d3.event.stopPropagation();
          hideTooltip(tooltip);
        });
      }

      const position = positionTooltip(event, tooltip);
      tooltip
        .style("left", position.left + "px")
        .style("top", position.top + "px");
    }

    function hideTooltip(tooltip) {
      tooltip.style("visibility", "hidden");
    }

    function drawBarsAndAxes({
      svg,
      g,
      x,
      y,
      z,
      width,
      height,
      margin,
      dataset,
      keys,
    }) {
      const tooltip = createTooltip();
      let pinnedBar = null;

      // Ensure all data points have values for all keys
      dataset.forEach((group) => {
        group.data.forEach((d) => {
          keys.forEach((k) => {
            if (typeof d[k] === "undefined") {
              d[k] = 0;
            }
          });
        });
      });

      // Calculate max height including stacked values
      const maxHeight =
        d3.max(
          dataset.flatMap((g) =>
            g.data.map((d) => keys.reduce((sum, key) => sum + (d[key] || 0), 0))
          )
        ) || 0; // Default to 0 if no data

      y.domain([0, maxHeight]).nice();
      z.domain(keys);

      // Group spacing and backgrounds
      const groupWidth = width / 3;
      const groupPadding = 20; // Add padding between groups

      // Add more distinct group backgrounds
      g.selectAll(".group-background")
        .data(dataset)
        .enter()
        .append("rect")
        .attr("class", "group-background")
        .attr("x", (d, i) => i * groupWidth)
        .attr("y", -20) // Extend up to include header
        .attr("width", groupWidth - groupPadding)
        .attr("height", height + 40) // Extra height for header
        .attr("fill", (d, i) => (i % 2 === 0 ? "#f8f9fa" : "#ffffff"))
        .attr("stroke", "#e9ecef")
        .attr("stroke-width", 1);

      // Draw the bars for each group
      dataset.forEach((group, groupIndex) => {
        const groupX = d3
          .scaleBand()
          .domain(group.data.map((d) => d.category))
          .range([
            groupIndex * groupWidth + groupPadding / 2,
            (groupIndex + 1) * groupWidth - groupPadding / 2,
          ])
          .padding(0.2); // Increased padding between bars

        const bars = g
          .append("g")
          .selectAll("g")
          .data(d3.stack().keys(keys)(group.data))
          .enter()
          .append("g")
          .attr("fill", (d) => z(d.key));

        bars
          .selectAll("rect")
          .data((d) => d)
          .enter()
          .append("rect")
          .attr("x", (d) => groupX(d.data.category))
          .attr("y", (d) => y(d[1]))
          .attr("height", (d) => y(d[0]) - y(d[1]))
          .attr("width", groupX.bandwidth())
          .attr("rx", 2)
          .attr("stroke", "#fff")
          .attr("stroke-width", 0.5)
          .attr("stroke-opacity", 0.8)
          .style("cursor", "pointer")
          .on("mouseover", function (event, d) {
            if (!pinnedBar) {
              d3.select(this)
                .attr("opacity", 0.8)
                .attr("stroke", "#666")
                .attr("stroke-width", 1);
              showTooltip(
                event,
                d,
                tooltip,
                d3.select(this.parentNode).datum().key,
                d.data
              );
            }
          })
          .on("mousemove", function (event) {
            if (!pinnedBar) {
              const position = positionTooltip(event, tooltip);
              tooltip
                .style("left", position.left + "px")
                .style("top", position.top + "px");
            }
          })
          .on("mouseout", function () {
            if (!pinnedBar) {
              d3.select(this)
                .attr("opacity", 1)
                .attr("stroke", "#fff")
                .attr("stroke-width", 0.5);
              hideTooltip(tooltip);
            }
          })
          .on("click", function (event, d) {
            event.stopPropagation();

            // If clicking the same bar, unpin it
            if (pinnedBar === this) {
              pinnedBar = null;
              d3.select(this)
                .attr("opacity", 1)
                .attr("stroke", "#fff")
                .attr("stroke-width", 0.5);
              hideTooltip(tooltip);
              return;
            }

            // Reset previous pinned bar if exists
            if (pinnedBar) {
              d3.select(pinnedBar)
                .attr("opacity", 1)
                .attr("stroke", "#fff")
                .attr("stroke-width", 0.5);
            }

            // Pin the new bar
            pinnedBar = this;
            d3.select(this)
              .attr("opacity", 0.8)
              .attr("stroke", "#666")
              .attr("stroke-width", 1);

            showTooltip(
              event,
              d,
              tooltip,
              d3.select(this.parentNode).datum().key,
              d.data,
              true
            );
          });

        // Improved category labels
        g.append("g")
          .attr("class", "category-labels")
          .selectAll("text")
          .data(group.data)
          .enter()
          .append("text")
          .attr("x", (d) => groupX(d.category) + groupX.bandwidth() / 2)
          .attr("y", height + 15)
          .attr("text-anchor", "end")
          .attr("transform", function (d) {
            return `rotate(-35 ${
              groupX(d.category) + groupX.bandwidth() / 2
            } ${height + 15})`;
          })
          .style("font-size", "11px")
          .text((d) => d.category);

        // Enhanced group headers
        g.append("text")
          .attr("x", groupIndex * groupWidth + groupWidth / 2)
          .attr("y", -25)
          .attr("text-anchor", "middle")
          .attr("font-weight", "bold")
          .attr("font-size", "14px")
          .text(group.group);
      });

      // Enhanced y-axis
      g.append("g")
        .attr("class", "axis")
        .call(d3.axisLeft(y).ticks(null, "s"))
        .append("text")
        .attr("x", 2)
        .attr("y", y(y.ticks().pop()) + 0.5)
        .attr("dy", "0.32em")
        .attr("fill", "#666")
        .attr("font-weight", "bold")
        .attr("text-anchor", "start")
        .text("Count");

      // Improved legend
      const legend = g
        .append("g")
        .attr("font-family", "sans-serif")
        .attr("font-size", "11px")
        .attr("text-anchor", "start")
        .selectAll("g")
        .data(keys.slice().reverse())
        .enter()
        .append("g")
        .attr("transform", (d, i) => `translate(${width + 10},${i * 25})`);

      legend
        .append("rect")
        .attr("x", 0)
        .attr("width", 18)
        .attr("height", 18)
        .attr("fill", z)
        .attr("rx", 2);

      legend
        .append("text")
        .attr("x", 24)
        .attr("y", 9)
        .attr("dy", "0.32em")
        .style("font-size", "11px")
        .text((d) => getGradeForCode(d));

      // Add click handler to unpin when clicking outside
      d3.select("body").on("click", function (event) {
        if (pinnedBar && !tooltip.node().contains(event.target)) {
          d3.select(pinnedBar)
            .attr("opacity", 1)
            .attr("stroke", "#fff")
            .attr("stroke-width", 0.5);
          hideTooltip(tooltip);
          pinnedBar = null;
        }
      });
    }

    //Filter Data
    d3.select(targetId).select("svg").remove();

    // Apply time filter
    var timeFrame = d3
      .select("input[name='characteristics-time-filter']:checked")
      .node().value;

    // Apply filters
    var filteredData = CommonFilters.filterByTime(inputData, timeFrame);

    // Get unique binned codes for the legend
    let uniqueBinnedCodes = [
      ...new Set(filteredData.map((item) => item.binned_code)),
    ];
    let filteredBinnedCodeDict = binnedCodeDict.filter((entry) =>
      uniqueBinnedCodes.includes(entry.binned_code)
    );
    const keys = filteredBinnedCodeDict.map((d) => d.binned_code);

    // Setup chart
    const { svg, g, x, y, z, width, height, margin } = setupChart(targetId);

    // Process and draw data
    const processedData = processData(filteredData);
    drawBarsAndAxes({
      svg,
      g,
      x,
      y,
      z,
      width,
      height,
      margin,
      dataset: processedData,
      keys,
    });
  }

  function determineData() {
    var discipline = d3
      .select("input[name='characteristics-discipline-filter']:checked")
      .node().value;

    let data;
    switch (discipline) {
      case "sport":
        data = sportPyramidData;
        break;
      case "trad":
        data = tradPyramidData;
        break;
      case "boulder":
        data = boulderPyramidData;
        break;
      default:
        console.error("Unknown discipline type");
        data = [];
    }

    return data;
  }

  function updateVisualization() {
    var data = determineData();
    characterVizChart("#performance-characteristics", data, binnedCodeDict);
  }

  d3.selectAll("input[name='characteristics-discipline-filter']").on(
    "change.updateVisualization",
    updateVisualization
  );

  d3.selectAll("input[name='characteristics-time-filter']").on(
    "change.updateVisualization",
    updateVisualization
  );

  updateVisualization();
});
