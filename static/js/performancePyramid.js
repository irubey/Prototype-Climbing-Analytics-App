document.addEventListener(
  "DOMContentLoaded",
  function initPerformancePyramid() {
    // Wait for required data to be loaded
    if (
      typeof window.sportPyramidData === "undefined" ||
      typeof window.binnedCodeDict === "undefined" ||
      typeof window.userTicksData === "undefined"
    ) {
      console.log("Waiting for data to load...", {
        sportPyramidData: window.sportPyramidData,
        binnedCodeDict: window.binnedCodeDict,
        userTicksData: window.userTicksData,
      });
      setTimeout(initPerformancePyramid, 100); // Retry in 100ms
      return;
    }

    // Define colors at the top level
    const colors = {
      green: {
        fill: "#3498db", // More professional blue
        stroke: "#2980b9", // Darker blue for stroke
      },
      grey: "#bdc3c7", // Darker grey for better visibility of excess
      gold: "#f1c40f", // Warmer gold for star
      text: {
        dark: "#2c3e50", // Dark blue-grey for main text
        light: "#7f8c8d", // Medium grey for secondary text
        highlight: "#2980b9", // Blue for highlighted text
      },
    };

    // Define pyramid progression types
    const pyramidTypes = {
      conservative: {
        name: "Conservative",
        description: "Wide base, gradual progression",
        goals: [1, 3, 6, 12, 24], // Wide base
      },
      normal: {
        name: "Normal",
        description: "Balanced progression",
        goals: [1, 3, 5, 8, 16], // Middle ground
      },
      fast: {
        name: "Fast",
        description: "Narrow base, rapid progression",
        goals: [1, 3, 4, 6, 9], // Steep pyramid
      },
    };

    // Make functions globally accessible
    window.pyramidVizChart = function (
      targetId,
      pyramidData,
      userTicksData,
      binnedCodeDict
    ) {
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
        if (!Array.isArray(dict)) {
          console.error("The input is not an array:", dict);
          return {};
        }
        var obj = {};
        dict.forEach(function (d) {
          obj[d.binned_code] = d.binned_grade;
        });
        return obj;
      }

      //Helper Functions -- Grade Pyramids
      function getTrianglePath(
        side,
        count,
        binned_grade,
        binned_code,
        isFlashOnsight,
        width,
        x,
        y,
        joinedDataArray,
        maxBinnedCode
      ) {
        if (count === 0 || count === null) {
          return null;
        }

        if (binned_code === maxBinnedCode && isFlashOnsight) {
          return null;
        }

        const xValue = x(count);
        const yValue = y(binned_grade);

        const x1 =
          side === "left" ? (width - xValue) / 2 - 1 : (width + xValue) / 2 + 1;

        const y1 = yValue + y.bandwidth();

        const nextBinnedCode = parseInt(binned_code) + 1;
        const nextBinnedCodeData = joinedDataArray.find(
          (d) => d.binned_code == nextBinnedCode
        );

        let nextGradeCount;
        if (isFlashOnsight) {
          nextGradeCount = nextBinnedCodeData
            ? nextBinnedCodeData.flashOnsightCount
            : null;
        } else {
          nextGradeCount = nextBinnedCodeData ? nextBinnedCodeData.count : null;
        }

        if (nextGradeCount > count) {
          return null;
        }

        let x2;
        if (nextGradeCount !== null) {
          x2 =
            side === "left"
              ? (width - x(nextGradeCount)) / 2
              : (width + x(nextGradeCount)) / 2;
        } else {
          x2 = side === "left" ? x1 + (y1 - yValue) : x1 - (y1 - yValue);
        }

        if (binned_code == maxBinnedCode) {
          x2 = width / 2;
        } else {
          // 45-degree angle check for non-maxBinnedCode triangles
          if (Math.abs(x2 - x1) > y1 - yValue) {
            x2 = side === "left" ? x1 + (y1 - yValue) : x1 - (y1 - yValue);
          }
        }

        const y2 = isFlashOnsight ? yValue : yValue - 1;
        const x3 = x1;
        const y3 = y2;

        return `M ${x1} ${y1} L ${x2} ${y2} L ${x3} ${y3} Z`;
      }

      function computeDataFrequencies(data) {
        var counts = {};
        data.forEach(function (d) {
          counts[d.binned_code] = (counts[d.binned_code] || 0) + 1;
        });
        return counts;
      }

      function calculategoalPyramid(data) {
        const maxBinnedCode = Math.max(...data.map((d) => d.binned_code));
        const paceType =
          d3.select("input[name='pyramid-pace']:checked").node()?.value ||
          "normal";
        const goals = pyramidTypes[paceType].goals;

        return [
          { binned_code: maxBinnedCode + 1, goalSends: goals[0] }, // Project grade
          { binned_code: maxBinnedCode, goalSends: goals[1] }, // Current max
          { binned_code: maxBinnedCode - 1, goalSends: goals[2] }, // One below
          { binned_code: maxBinnedCode - 2, goalSends: goals[3] }, // Two below
          { binned_code: maxBinnedCode - 3, goalSends: goals[4] }, // Three below
        ];
      }

      function processTimeSeriesData(data) {
        // Sort data by tick_date
        const sortedData = [...data].sort(
          (a, b) => new Date(a.tick_date) - new Date(b.tick_date)
        );

        // Create accumulating counts over time
        const timeSeriesCounts = sortedData.reduce((acc, send) => {
          const lastCount =
            acc.length > 0 ? { ...acc[acc.length - 1].counts } : {};
          lastCount[send.binned_code] = (lastCount[send.binned_code] || 0) + 1;

          acc.push({
            date: new Date(send.tick_date),
            counts: lastCount,
          });

          return acc;
        }, []);

        return timeSeriesCounts;
      }

      function animateBars(bars, timeSeriesData, width, x, duration = 1000) {
        const startDelay = 100;
        const excessDelay = startDelay + duration + 50;
        const hasExcessBars = bars.nodes().some((node) => {
          const bar = d3.select(node);
          return bar.selectAll("rect[fill='" + colors.grey + "']").size() > 0;
        });
        const starDelay = hasExcessBars
          ? excessDelay + duration + 50
          : startDelay + duration + 50;
        const starDuration = 500;
        const labelDelay = starDelay + starDuration + 50;

        // Hide all stats initially
        d3.selectAll(".grade-stats text").style("opacity", 0);
        d3.selectAll(".column-header").style("opacity", 0);

        // Animate regular bars
        bars.each(function (d) {
          const bar = d3.select(this);

          if (d.isProjectGrade) {
            // Star animation
            const star = bar.select("image");
            if (star.size()) {
              star
                .transition()
                .delay(starDelay)
                .duration(starDuration)
                .ease(d3.easeBounceOut)
                .style("opacity", 1)
                .style("transform", "scale(1)")
                .on("start", function () {
                  d3.select(this)
                    .style("filter", "drop-shadow(0 0 5px gold)")
                    .transition()
                    .delay(starDuration)
                    .duration(200)
                    .style("filter", "drop-shadow(0 1px 2px rgba(0,0,0,0.1))");
                });
            }
          } else {
            // Animate progress bars
            const progressBar = bar.select(
              "rect[fill='" + colors.green.fill + "']"
            );
            const excessBars = bar.selectAll(
              "rect[fill='" + colors.grey + "']"
            );

            if (progressBar.size()) {
              const finalWidth = progressBar.attr("width");
              const finalX = progressBar.attr("x");
              const centerX = width / 2;

              progressBar
                .attr("x", centerX)
                .attr("width", 0)
                .transition()
                .delay(startDelay)
                .duration(duration)
                .ease(d3.easeQuadInOut)
                .attr("width", finalWidth)
                .attr("x", finalX);
            }

            if (excessBars.size()) {
              const leftExcess = excessBars.filter(function () {
                return d3.select(this).attr("x") < width / 2;
              });
              const rightExcess = excessBars.filter(function () {
                return d3.select(this).attr("x") >= width / 2;
              });

              // Get the edges of the ideal bar
              const idealBarLeft = (width - x(d.goalSends)) / 2;
              const idealBarRight = (width + x(d.goalSends)) / 2;

              // Animate both sides simultaneously after main bar completes
              if (leftExcess.size()) {
                const leftBar = leftExcess.node();
                const finalLeftWidth = d3.select(leftBar).attr("width");
                const finalLeftX = d3.select(leftBar).attr("x");

                d3.select(leftBar)
                  .attr("x", idealBarLeft)
                  .attr("width", 0)
                  .transition()
                  .delay(excessDelay)
                  .duration(duration)
                  .ease(d3.easeQuadInOut)
                  .attr("width", finalLeftWidth)
                  .attr("x", finalLeftX);
              }

              if (rightExcess.size()) {
                const rightBar = rightExcess.node();
                const finalRightWidth = d3.select(rightBar).attr("width");

                d3.select(rightBar)
                  .attr("x", idealBarRight)
                  .attr("width", 0)
                  .transition()
                  .delay(excessDelay)
                  .duration(duration)
                  .ease(d3.easeQuadInOut)
                  .attr("width", finalRightWidth);
              }
            }
          }
        });

        // Fade in all stats and headers after animations complete
        d3.selectAll(".grade-stats text")
          .transition()
          .delay(labelDelay)
          .duration(200)
          .style("opacity", 1);

        d3.selectAll(".column-header")
          .transition()
          .delay(labelDelay)
          .duration(200)
          .style("opacity", 1);
      }

      function calculateGradeStats(userTicksData, binned_code) {
        // Filter user ticks for this grade
        const gradeAttempts = userTicksData.filter(
          (d) => d.binned_code === binned_code
        );

        // Calculate total attempts based on length_category
        const totalAttempts = gradeAttempts.reduce((sum, tick) => {
          if (tick.length_category === "multipitch") {
            return sum + 1; // Each record counts as 1 attempt for multipitch
          } else {
            return sum + (tick.pitches || 1); // Sum pitches for single pitch
          }
        }, 0);

        // Count successful sends (using pyramid data since it's already filtered for sends)
        const sends = pyramidData.filter(
          (d) => d.binned_code === binned_code
        ).length;

        // Calculate send rate
        const sendRate =
          totalAttempts > 0 ? Math.round((sends / totalAttempts) * 100) : 0;

        // Get last send date
        const lastSend =
          sends > 0
            ? pyramidData.find((d) => d.binned_code === binned_code)
                ?.season_category || "-"
            : "-";

        return { totalAttempts, sends, sendRate, lastSend };
      }

      function createPyramidVisualization(
        targetId,
        pyramidData,
        userTicksData,
        binnedCodeDict
      ) {
        // Clear existing chart
        d3.select(targetId).select("svg").remove();

        // Process and prepare data first
        const binnedCodeObj = convertDictToObj(binnedCodeDict);
        const timeFrame = d3
          .select("input[name='performance-pyramid-time-filter']:checked")
          .node().value;

        // Get filtered data for stats and counts
        const filteredUserTicks = CommonFilters.filterByTime(
          userTicksData,
          timeFrame
        );
        const filteredPyramidData = CommonFilters.filterByTime(
          pyramidData,
          timeFrame
        );

        // Use all-time data for structure only
        const goalPyramid = calculategoalPyramid(pyramidData); // Use all-time data for structure

        // Get time-filtered counts for display
        const counts = computeDataFrequencies(filteredPyramidData);

        // Convert filtered counts to array format
        let data = Object.entries(counts).map(([key, value]) => ({
          binned_code: parseInt(key),
          count: value,
        }));

        // Create joined data array with grades and goal sends
        const joinedData = goalPyramid.map((goal) => {
          // Calculate stats from filtered user ticks
          const stats = calculateGradeStats(
            filteredUserTicks,
            goal.binned_code
          );

          return {
            binned_code: goal.binned_code,
            binned_grade: binnedCodeObj[goal.binned_code],
            count: stats.sends || 0, // Use sends count for the pyramid
            totalAttempts: stats.totalAttempts || 0, // Store total attempts
            goalSends: goal.goalSends,
            sendRate: stats.sendRate,
            lastSend: stats.lastSend,
            isProjectGrade: goal === goalPyramid[0], // First item in goalPyramid is always the project grade
          };
        });

        // Setup margins and dimensions
        const margin = { top: 40, right: 600, bottom: 20, left: 20 };
        const width = 1000 - margin.left - margin.right;
        const height = 220 - margin.top - margin.bottom;

        // Create SVG container with background
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
          .append("g")
          .attr("transform", `translate(${margin.left},${margin.top})`);

        // Add subtle background
        svg
          .append("rect")
          .attr("width", width + margin.right)
          .attr("height", height + margin.bottom)
          .attr("fill", "#f8f9fa")
          .attr("rx", 8);

        // Create scales
        const x = createLinearScale([0, width]);
        const y = createBandScale([height, 0], 0.2);

        // Set scales domains after data is processed
        const maxCount = Math.max(
          d3.max(joinedData, (d) => d.count),
          d3.max(joinedData, (d) => d.goalSends)
        );
        x.domain([0, maxCount * 1.2]); // Add 20% padding
        y.domain(joinedData.map((d) => d.binned_grade).reverse());

        console.log("Y Domain Debug:", {
          joinedData: joinedData,
          yDomain: y.domain(),
          binned_grades: joinedData.map((d) => d.binned_grade),
          binned_codes: joinedData.map((d) => d.binned_code),
        });

        // Process time series data
        const timeSeriesData = processTimeSeriesData(filteredUserTicks);

        // Calculate the leftmost and rightmost edges before creating labels
        const leftmostEdge = d3.min(joinedData, (d) => {
          const barWidth = Math.max(x(d.count || 0), x(d.goalSends || 0));
          return (width - barWidth) / 2;
        });

        const rightmostEdge = d3.max(joinedData, (d) => {
          const barWidth = Math.max(x(d.count || 0), x(d.goalSends || 0));
          return (width + barWidth) / 2;
        });

        // Add horizontal lines for each grade - extending full width
        svg
          .selectAll(".grade-line")
          .data(joinedData)
          .enter()
          .append("line")
          .attr("class", "grade-line")
          .attr("x1", 0) // Start from left edge of bars
          .attr("x2", width + margin.right) // Extend right through the data table
          .attr("y1", (d) => y(d.binned_grade) + y.bandwidth())
          .attr("y2", (d) => y(d.binned_grade) + y.bandwidth())
          .attr("stroke", "#e9ecef")
          .attr("stroke-width", 1);

        // Create bars first (existing code)
        const bars = svg
          .selectAll(".bar")
          .data(joinedData)
          .enter()
          .append("g")
          .attr("class", "bar");

        // Add main bars with different states
        bars.each(function (d) {
          const bar = d3.select(this);
          const isOvergoal = d.count > d.goalSends;
          const baseRadius = 2; // Slight rounding on bars

          if (d.isProjectGrade) {
            // Project grade - star
            const starHeight = y.bandwidth() * 0.7; // Slightly smaller star
            const starWidth = starHeight;

            bar
              .append("image")
              .attr("href", "/static/images/capstone.svg")
              .attr("x", (width - starWidth) / 2)
              .attr("y", y(d.binned_grade) + (y.bandwidth() - starHeight) / 2)
              .attr("width", starWidth)
              .attr("height", starHeight)
              .style("opacity", 0)
              .style("transform", "scale(0.5)")
              .style("filter", "drop-shadow(0 1px 2px rgba(0,0,0,0.1))")
              .style("transition", "all 0.3s ease");
          } else {
            // Goal outline
            bar
              .append("rect")
              .attr("x", (width - x(d.goalSends)) / 2)
              .attr("y", y(d.binned_grade))
              .attr("width", x(d.goalSends))
              .attr("height", y.bandwidth())
              .attr("rx", baseRadius)
              .attr("ry", baseRadius)
              .attr("fill", "none")
              .attr("stroke", colors.green.stroke)
              .attr("stroke-width", 1)
              .attr("stroke-dasharray", "3,3")
              .style("transition", "all 0.3s ease");

            // Progress fill
            const achievedAmount = Math.min(d.count, d.goalSends);
            if (achievedAmount > 0) {
              bar
                .append("rect")
                .attr("x", (width - x(achievedAmount)) / 2)
                .attr("y", y(d.binned_grade))
                .attr("width", x(achievedAmount))
                .attr("height", y.bandwidth())
                .attr("rx", baseRadius)
                .attr("ry", baseRadius)
                .attr("fill", colors.green.fill)
                .attr("fill-opacity", 0.9)
                .style("filter", "drop-shadow(0 1px 2px rgba(0,0,0,0.1))")
                .style("transition", "all 0.3s ease");
            }

            // Excess bars
            if (d.count > d.goalSends) {
              const excessSends = d.count - d.goalSends;
              const halfExcess = excessSends / 2;

              ["left", "right"].forEach((side) => {
                bar
                  .append("rect")
                  .attr(
                    "x",
                    side === "left"
                      ? (width - x(d.goalSends)) / 2 - x(halfExcess)
                      : (width + x(d.goalSends)) / 2
                  )
                  .attr("y", y(d.binned_grade))
                  .attr("width", x(halfExcess))
                  .attr("height", y.bandwidth())
                  .attr("rx", baseRadius)
                  .attr("ry", baseRadius)
                  .attr("fill", colors.grey)
                  .attr("fill-opacity", 0.95)
                  .style("filter", "drop-shadow(0 1px 1px rgba(0,0,0,0.05))")
                  .style("transition", "all 0.3s ease");
              });
            }
          }
        });

        // Add header labels
        const headerY = -15;
        const headerStyle = {
          fontSize: "12px",
          fill: colors.text.light,
          fontWeight: "500",
          fontFamily: "Inter, -apple-system, sans-serif",
          letterSpacing: "0.01em",
        };

        const columnSpacing = 85;
        const firstColumnX = rightmostEdge + 40;
        const columnHeaders = [
          { text: "Grade", x: firstColumnX },
          { text: "Sends", x: firstColumnX + columnSpacing },
          { text: "Goal Sends", x: firstColumnX + columnSpacing * 2 },
          { text: "Total Attempts", x: firstColumnX + columnSpacing * 3 },
          { text: "Send Rate", x: firstColumnX + columnSpacing * 4 },
          { text: "Last Send", x: firstColumnX + columnSpacing * 5 },
        ];

        // Add column headers
        columnHeaders.forEach((header) => {
          svg
            .append("text")
            .attr("class", "column-header")
            .attr("x", header.x)
            .attr("y", headerY)
            .attr("text-anchor", "middle")
            .text(header.text)
            .style("font-size", headerStyle.fontSize)
            .style("fill", headerStyle.fill)
            .style("font-weight", headerStyle.fontWeight)
            .style("font-family", headerStyle.fontFamily)
            .style("letter-spacing", headerStyle.letterSpacing)
            .style("opacity", 0);
        });

        // Add stats section for each row
        const statsGroup = bars
          .append("g")
          .attr("class", "grade-stats")
          .attr(
            "transform",
            (d) => `translate(0,${y(d.binned_grade) + y.bandwidth() / 2})`
          );

        // Style all text elements consistently
        statsGroup
          .selectAll("text")
          .style("font-family", headerStyle.fontFamily)
          .style("font-size", headerStyle.fontSize)
          .style("letter-spacing", headerStyle.letterSpacing);

        // Add Grade
        statsGroup
          .append("text")
          .attr("x", firstColumnX)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => d.binned_grade)
          .style("font-weight", "600")
          .style("fill", (d) =>
            d.isProjectGrade ? colors.gold : colors.text.dark
          )
          .style("opacity", 0)
          .attr("class", "column-header");

        // Add Sends
        statsGroup
          .append("text")
          .attr("x", firstColumnX + columnSpacing)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => {
            const sends = d.count === 0 ? "-" : d.count;
            const complete = d.count >= d.goalSends ? " ✓" : "";
            return sends === "-" ? sends : sends + complete;
          })
          .style("font-weight", "500")
          .style("fill", (d) =>
            d.count >= d.goalSends ? colors.green.fill : colors.text.light
          )
          .style("opacity", 0)
          .attr("class", "column-header")
          .style("font-feature-settings", "tnum");

        // Add Goal
        statsGroup
          .append("text")
          .attr("x", firstColumnX + columnSpacing * 2)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => (d.isProjectGrade ? "1" : d.goalSends))
          .style("font-weight", "400")
          .style("fill", colors.text.light)
          .style("opacity", 0)
          .attr("class", "column-header")
          .style("font-feature-settings", "tnum");

        // Add Total Attempts
        statsGroup
          .append("text")
          .attr("x", firstColumnX + columnSpacing * 3)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => (d.totalAttempts === 0 ? "-" : d.totalAttempts))
          .style("opacity", 0)
          .attr("class", "column-header")
          .style("font-feature-settings", "tnum");

        // Add Send Rate
        statsGroup
          .append("text")
          .attr("x", firstColumnX + columnSpacing * 4)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => (d.sendRate === 0 ? "-" : `${d.sendRate}%`))
          .style("opacity", 0)
          .attr("class", "column-header")
          .style("font-feature-settings", "tnum");

        // Add Last Send
        statsGroup
          .append("text")
          .attr("x", firstColumnX + columnSpacing * 5)
          .attr("dy", "0.32em")
          .attr("text-anchor", "middle")
          .text((d) => {
            if (d.lastSend === "-") return "-";
            const [season, year] = d.lastSend.split(", ");
            return `${season} ${year.split("-")[0]}`;
          })
          .style("opacity", 0)
          .attr("class", "column-header")
          .style("font-feature-settings", "tnum");

        // Update text styling for stats
        statsGroup
          .selectAll("text")
          .style("font-family", "Inter, -apple-system, sans-serif")
          .style("font-size", "12px");

        // Style grade column
        statsGroup
          .select("text:nth-child(1)")
          .style("font-weight", "600")
          .style("fill", (d) =>
            d.isProjectGrade ? colors.gold : colors.text.dark
          );

        // Style sends/goal column
        statsGroup
          .select("text:nth-child(2)")
          .style("font-weight", "500")
          .style("fill", (d) =>
            d.count >= d.goalSends ? colors.green.fill : colors.text.light
          );

        // Style other columns
        statsGroup
          .selectAll("text:nth-child(n+3)")
          .style("fill", colors.text.light)
          .style("font-weight", "400");

        // Remove old labels
        svg.selectAll(".bar-labels").remove();
        svg.selectAll(".right-labels").remove();

        // Start animation
        animateBars(bars, timeSeriesData, width, x);
      }

      createPyramidVisualization(
        targetId,
        pyramidData,
        userTicksData,
        binnedCodeDict
      );
    };

    window.determineData = function () {
      var discipline = d3
        .select("input[name='performance-pyramid-discipline-filter']:checked")
        .node().value;

      console.log("Selected discipline:", discipline);

      let pyramidData;
      switch (discipline) {
        case "sport":
          pyramidData = window.sportPyramidData;
          break;
        case "trad":
          pyramidData = window.tradPyramidData;
          break;
        case "boulder":
          pyramidData = window.boulderPyramidData;
          break;
        default:
          console.error("Unknown discipline type");
          pyramidData = [];
      }

      console.log("Pyramid Data for visualization:", {
        discipline,
        pyramidData,
        userTicksData: window.userTicksData,
        binnedCodeDict: window.binnedCodeDict,
      });

      return { pyramidData, userTicksData: window.userTicksData };
    };

    // Function to update visualization
    function updateVisualization() {
      console.log("Starting visualization update");
      const data = determineData();

      // Check if data is valid before creating visualization
      if (!data.pyramidData || !Array.isArray(data.pyramidData)) {
        console.error("Invalid pyramid data:", data.pyramidData);
        return;
      }

      if (!window.binnedCodeDict || !Array.isArray(window.binnedCodeDict)) {
        console.error("Invalid binned code dict:", window.binnedCodeDict);
        return;
      }

      pyramidVizChart(
        "#performance-pyramid",
        data.pyramidData,
        data.userTicksData,
        window.binnedCodeDict
      );
    }

    // Add event listeners for all filters
    d3.selectAll("input[name='performance-pyramid-discipline-filter']").on(
      "change",
      updateVisualization
    );

    d3.selectAll("input[name='performance-pyramid-time-filter']").on(
      "change",
      updateVisualization
    );

    d3.selectAll("input[name='pyramid-pace']").on(
      "change",
      updateVisualization
    );

    // Initial visualization
    updateVisualization();
  }
);
