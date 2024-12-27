function locationTreeChart(userTicksData, targetId) {
  const MARGIN = { top: 10, right: 10, bottom: 10, left: 10 };

  function processData(data) {
    // Create maps to store node counts and pitches
    const nodeCounts = new Map();
    const nodePitches = new Map();
    const nodeSpecificPitches = new Map(); // For pitches at this specific level

    // Process each location
    data.forEach((tick) => {
      if (!tick.location_raw) return;
      const parts = tick.location_raw.split(">").map((p) => p.trim());

      // Count occurrences and sum pitches for each path
      for (let i = 1; i <= parts.length; i++) {
        const path = parts.slice(0, i).join(" > ");
        const specificPart = parts[i - 1]; // The specific part at this level

        // Increment total counts
        nodeCounts.set(path, (nodeCounts.get(path) || 0) + 1);
        nodePitches.set(
          path,
          (nodePitches.get(path) || 0) + (tick.pitches || 0)
        );

        // Track pitches for specific part
        const key = path + "|" + specificPart;
        nodeSpecificPitches.set(
          key,
          (nodeSpecificPitches.get(key) || 0) + (tick.pitches || 0)
        );
      }
    });

    // Create hierarchical structure
    const root = { name: "All Locations", children: new Map() };

    data.forEach((tick) => {
      if (!tick.location_raw) return;
      const parts = tick.location_raw.split(">").map((p) => p.trim());
      let currentNode = root;
      let currentPath = "";

      parts.forEach((part, i) => {
        currentPath = currentPath ? currentPath + " > " + part : part;
        if (!currentNode.children.has(part)) {
          const key = currentPath + "|" + part;
          currentNode.children.set(part, {
            name: part,
            fullPath: currentPath,
            count: nodeCounts.get(currentPath),
            totalPitches: nodePitches.get(currentPath),
            specificPitches: nodeSpecificPitches.get(key) || 0,
            children: new Map(),
          });
        }
        currentNode = currentNode.children.get(part);
      });
    });

    function convertToArray(node) {
      const result = {
        name: node.name,
        fullPath: node.fullPath,
        count: node.count,
        totalPitches: node.totalPitches,
        specificPitches: node.specificPitches,
      };

      if (node.children.size > 0) {
        // Convert all children, sorted by total pitches for better layout
        result.children = Array.from(node.children.values())
          .sort((a, b) => b.totalPitches - a.totalPitches)
          .map(convertToArray);
      }

      return result;
    }

    return convertToArray(root);
  }

  function getTooltipContent(d) {
    if (d.data.name === "All Locations") {
      return `<div style="font-family: sans-serif;">
                <strong>All Locations</strong><br/>
                Total Climbs: ${d.value || 0}<br/>
                Total Pitches: ${d.data.totalPitches || 0}
              </div>`;
    }

    const percentage = d.parent
      ? Math.round((d.data.totalPitches / d.parent.data.totalPitches) * 100)
      : 100;

    return `<div style="font-family: sans-serif;">
              <strong>${d.data.name}</strong><br/>
              ${
                d.data.fullPath
                  ? `<small style="color: #666;">${d.data.fullPath}</small><br/>`
                  : ""
              }
              Pitches climbed at this location: ${
                d.data.specificPitches || 0
              }<br/>
              ${
                d.parent
                  ? `Percentage of ${d.parent.data.name}: ${percentage}%`
                  : ""
              }
            </div>`;
  }

  function createVisualization(data) {
    // Clear any existing SVG
    d3.select(targetId).selectAll("svg").remove();

    // Create tooltip if it doesn't exist
    let tooltip = d3.select("body").select(".tree-tooltip");
    if (tooltip.empty()) {
      tooltip = d3
        .select("body")
        .append("div")
        .attr("class", "tree-tooltip")
        .style("position", "absolute")
        .style("visibility", "hidden")
        .style("background-color", "white")
        .style("padding", "10px")
        .style("border", "1px solid #ddd")
        .style("border-radius", "4px")
        .style("font-size", "12px")
        .style("pointer-events", "none")
        .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
        .style("z-index", "1000");
    }

    // Create SVG with dimensions matching location race chart
    const container = d3.select(targetId);
    const containerWidth = container.node().getBoundingClientRect().width;
    const chartWidth = Math.min(
      containerWidth - MARGIN.left - MARGIN.right,
      600
    );
    const height = chartWidth;
    const diameter = Math.min(chartWidth, height);
    const radius = diameter * 0.45;

    // Create hierarchical data
    const root = d3
      .hierarchy(data)
      .sum((d) => d.totalPitches)
      .sort((a, b) => b.data.totalPitches - a.data.totalPitches);

    // Create tree layout with maximized spacing
    const treeLayout = d3.cluster().size([2 * Math.PI, radius]);

    // Apply the layout
    treeLayout(root);

    // Create color scale for top-level nodes
    const topLevelNodes = root.children || [];
    const color = d3
      .scaleOrdinal(d3.schemeCategory10)
      .domain(topLevelNodes.map((d) => d.data.name));

    // Calculate legend dimensions
    const legendSpacing = 20;
    const legendRectSize = 10;
    const legendPadding = 20;
    const legendWidth =
      d3.max(topLevelNodes, (d) => d.data.name.length) * 8 +
      legendRectSize +
      10;
    const legendHeight = topLevelNodes.length * legendSpacing;

    // Add extra width for legend
    const totalWidth = chartWidth + legendWidth + legendPadding * 3;

    const svg = container
      .append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", `0 0 ${totalWidth} ${height}`)
      .attr("preserveAspectRatio", "xMidYMid meet")
      .append("g")
      .attr("transform", `translate(${chartWidth / 2},${height / 2})`);

    // Function to get the color based on top-level ancestor
    function getNodeColor(d) {
      if (d.data.name === "All Locations") return "#999";
      // Find the top-level ancestor
      let node = d;
      while (node.parent && node.parent.data.name !== "All Locations") {
        node = node.parent;
      }
      return color(node.data.name);
    }

    // Sort nodes to minimize crossings
    function sortNodes(node) {
      if (!node.children) return;

      // Sort children by their percentage contribution to parent
      node.children.sort((a, b) => {
        // Calculate percentages
        const aPercentage =
          (a.data.totalPitches / node.data.totalPitches) * 100;
        const bPercentage =
          (b.data.totalPitches / node.data.totalPitches) * 100;
        // Sort by percentage (higher percentages will be placed counterclockwise)
        return bPercentage - aPercentage;
      });

      // Recursively sort children
      node.children.forEach(sortNodes);
    }
    sortNodes(root);

    // Create links
    const link = svg
      .selectAll(".link")
      .data(root.links())
      .join("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", (d) => getNodeColor(d.target))
      .attr("stroke-opacity", (d) => {
        // Calculate child's percentage of parent's total
        const percentage =
          (d.target.data.totalPitches / d.source.data.totalPitches) * 100;
        // Map percentage to opacity range (0.1 to 0.8)
        return 0.1 + (percentage / 100) * 0.7;
      })
      .attr("stroke-width", (d) => {
        // Calculate child's percentage of parent's total
        const percentage =
          (d.target.data.totalPitches / d.source.data.totalPitches) * 100;
        // Base width on percentage, with a minimum to ensure visibility
        return Math.max(0.5, percentage / 20);
      })
      .attr("d", (d) => {
        const sourceAngle = d.source.x;
        const targetAngle = d.target.x;
        const sourceRadius = d.source.y;
        const targetRadius = d.target.y;

        // Convert to Cartesian coordinates
        const sx = sourceRadius * Math.cos(sourceAngle - Math.PI / 2);
        const sy = sourceRadius * Math.sin(sourceAngle - Math.PI / 2);
        const tx = targetRadius * Math.cos(targetAngle - Math.PI / 2);
        const ty = targetRadius * Math.sin(targetAngle - Math.PI / 2);

        return `M${sx},${sy}L${tx},${ty}`;
      });

    // Create nodes
    const node = svg
      .selectAll(".node")
      .data(root.descendants())
      .join("g")
      .attr(
        "class",
        (d) => `node ${d.children ? "node--internal" : "node--leaf"}`
      )
      .attr("transform", (d) => {
        const angle = d.x - Math.PI / 2;
        return `translate(${d.y * Math.cos(angle)},${d.y * Math.sin(angle)})`;
      });

    // Add circles to nodes
    node
      .append("circle")
      .attr("r", (d) => {
        // Base size on depth (nesting level)
        if (d.depth === 0) return 8; // Root node
        if (d.depth === 1) return 6; // First level
        if (d.depth === 2) return 4; // Second level
        return 2.5; // All deeper levels
      })
      .attr("fill", (d) => getNodeColor(d))
      .attr("fill-opacity", 1)
      .attr("stroke", "#fff")
      .attr("stroke-width", (d) => (d.depth === 0 ? 0.5 : 0.2));

    // Add hover interactions
    node
      .on("mouseover", function (event, d) {
        // Get both ancestors and descendants
        const ancestors = d.ancestors();
        const descendants = d.descendants();
        const relatedNodes = new Set([...ancestors, ...descendants]);

        // Fade all links, then highlight relevant ones
        link
          .style("stroke-opacity", (l) => {
            // Check if link is in the path from root to target or in subtree
            if (
              (ancestors.includes(l.source) && ancestors.includes(l.target)) ||
              (descendants.includes(l.source) && descendants.includes(l.target))
            ) {
              return 0.8;
            }
            return 0.05;
          })
          .style("stroke-width", (l) => {
            const baseWidth = Math.max(0.5, 1 / Math.sqrt(l.target.depth || 1));
            if (
              (ancestors.includes(l.source) && ancestors.includes(l.target)) ||
              (descendants.includes(l.source) && descendants.includes(l.target))
            ) {
              return baseWidth * 2;
            }
            return baseWidth * 0.5;
          });

        // Fade all nodes, then highlight related ones
        node
          .select("circle")
          .style("fill-opacity", (n) => (relatedNodes.has(n) ? 1 : 0.1));

        tooltip
          .style("visibility", "visible")
          .style("left", event.pageX + 10 + "px")
          .style("top", event.pageY - 28 + "px")
          .html(getTooltipContent(d));
      })
      .on("mouseout", function () {
        // Reset to default high-visibility state
        link.style("stroke-opacity", 0.8).style("stroke-width", (d) => {
          const depthScale = 1 / Math.sqrt(d.target.depth || 1);
          const valueScale = Math.sqrt((d.target.value || 1) / root.value);
          return Math.max(0.5, depthScale * (1 + valueScale));
        });

        node.select("circle").style("fill-opacity", 1);

        tooltip.style("visibility", "hidden");
      });

    // Add legend
    // Position legend on right side with proper spacing
    const legendX = chartWidth / 2 + legendPadding;
    const legendY = -legendHeight / 2;

    const legend = svg
      .selectAll(".legend")
      .data(topLevelNodes)
      .enter()
      .append("g")
      .attr("class", "legend")
      .attr(
        "transform",
        (d, i) => `translate(${legendX},${legendY + i * legendSpacing})`
      );

    // Add colored rectangles
    legend
      .append("rect")
      .attr("width", legendRectSize)
      .attr("height", legendRectSize)
      .style("fill", (d) => color(d.data.name))
      .style("stroke", (d) => color(d.data.name))
      .style("cursor", "pointer");

    // Add text labels
    legend
      .append("text")
      .attr("x", legendRectSize + 5)
      .attr("y", legendRectSize - 1)
      .text((d) => d.data.name)
      .style("font-size", "12px")
      .style("cursor", "pointer");

    // Add hover interactions to legend
    legend
      .on("mouseover", function (event, d) {
        // Get both ancestors and descendants of the corresponding node
        const ancestors = d.ancestors();
        const descendants = d.descendants();
        const relatedNodes = new Set([...ancestors, ...descendants]);

        // Fade all links, then highlight relevant ones
        link
          .style("stroke-opacity", (l) => {
            if (
              (ancestors.includes(l.source) && ancestors.includes(l.target)) ||
              (descendants.includes(l.source) && descendants.includes(l.target))
            ) {
              return 0.8;
            }
            return 0.05;
          })
          .style("stroke-width", (l) => {
            const baseWidth = Math.max(0.5, 1 / Math.sqrt(l.target.depth || 1));
            if (
              (ancestors.includes(l.source) && ancestors.includes(l.target)) ||
              (descendants.includes(l.source) && descendants.includes(l.target))
            ) {
              return baseWidth * 2;
            }
            return baseWidth * 0.5;
          });

        // Fade all nodes, then highlight related ones
        node
          .select("circle")
          .style("fill-opacity", (n) => (relatedNodes.has(n) ? 1 : 0.1));

        // Highlight the legend item
        legend
          .selectAll("rect")
          .style("opacity", (item) => (item === d ? 1 : 0.1));
        legend
          .selectAll("text")
          .style("opacity", (item) => (item === d ? 1 : 0.1));
      })
      .on("mouseout", function () {
        // Reset link styles
        link.style("stroke-opacity", 0.8).style("stroke-width", (d) => {
          const depthScale = 1 / Math.sqrt(d.target.depth || 1);
          const valueScale = Math.sqrt((d.target.value || 1) / root.value);
          return Math.max(0.5, depthScale * (1 + valueScale));
        });

        // Reset node styles
        node.select("circle").style("fill-opacity", 1);

        // Reset legend styles
        legend.selectAll("rect").style("opacity", 1);
        legend.selectAll("text").style("opacity", 1);
      });
  }

  // Process data and create visualization
  const hierarchicalData = processData(userTicksData);
  createVisualization(hierarchicalData);
}
