function locationNetwork(userTicksData, targetId) {
  // Set dimensions
  const width = 960;
  const height = 600;

  // Process data to create nodes and links
  function processData(data) {
    const locations = new Map();
    const disciplines = new Set();
    const links = new Map();

    // Process each tick
    data.forEach((tick) => {
      // Skip entries without location or discipline
      if (!tick.location || !tick.discipline) return;

      const location = tick.location.trim();
      const discipline = tick.discipline;

      // Add to locations map with count and disciplines
      if (!locations.has(location)) {
        locations.set(location, {
          id: location,
          group: "location",
          count: 0,
          disciplines: new Set(),
        });
      }
      const loc = locations.get(location);
      loc.count++;
      loc.disciplines.add(discipline);

      // Add discipline
      disciplines.add(discipline);

      // Create/update link
      const linkKey = `${location}-${discipline}`;
      if (!links.has(linkKey)) {
        links.set(linkKey, {
          source: location,
          target: discipline,
          value: 0,
        });
      }
      links.get(linkKey).value++;
    });

    return {
      nodes: [
        ...Array.from(locations.values()),
        ...Array.from(disciplines).map((d) => ({
          id: d,
          group: "discipline",
          count: 0,
        })),
      ],
      links: Array.from(links.values()),
    };
  }

  // Clear any existing SVG
  d3.select(targetId).selectAll("svg").remove();

  // Create SVG with responsive sizing
  const container = d3.select(targetId);
  const containerWidth = container.node().getBoundingClientRect().width;
  const containerHeight = Math.min(containerWidth * 0.6, height);

  const svg = container
    .append("svg")
    .attr("width", "100%")
    .attr("height", containerHeight)
    .attr(
      "viewBox",
      `${-containerWidth / 2} ${
        -containerHeight / 2
      } ${containerWidth} ${containerHeight}`
    );

  const graph = processData(userTicksData);

  // Create forces
  const simulation = d3
    .forceSimulation(graph.nodes)
    .force(
      "link",
      d3
        .forceLink(graph.links)
        .id((d) => d.id)
        .distance(100)
    )
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter())
    .force(
      "collide",
      d3
        .forceCollide()
        .radius((d) =>
          d.group === "location" ? Math.sqrt(d.count) * 2 + 20 : 30
        )
    );

  // Create links
  const link = svg
    .append("g")
    .selectAll("line")
    .data(graph.links)
    .join("line")
    .attr("stroke", "#999")
    .attr("stroke-opacity", 0.6)
    .attr("stroke-width", (d) => Math.sqrt(d.value));

  // Create nodes
  const node = svg
    .append("g")
    .selectAll("g")
    .data(graph.nodes)
    .join("g")
    .call(drag(simulation));

  // Add circles to nodes
  node
    .append("circle")
    .attr("r", (d) =>
      d.group === "location" ? Math.sqrt(d.count) * 2 + 10 : 20
    )
    .attr("fill", (d) =>
      d.group === "location"
        ? d3.interpolateYlOrRd(
            d.count / d3.max(graph.nodes, (n) => n.count || 0)
          )
        : d3.schemeSet2[graph.nodes.indexOf(d) % 10]
    );

  // Add labels to nodes
  node
    .append("text")
    .text((d) => d.id)
    .attr("x", 0)
    .attr("y", (d) =>
      d.group === "location" ? -(Math.sqrt(d.count) * 2 + 12) : -25
    )
    .attr("text-anchor", "middle")
    .style("font-size", (d) => (d.group === "location" ? "10px" : "12px"))
    .style("font-weight", (d) =>
      d.group === "discipline" ? "bold" : "normal"
    );

  // Add hover interaction
  node
    .on("mouseover", function (event, d) {
      const tooltip = d3.select("#network-tooltip");
      tooltip.transition().duration(200).style("opacity", 0.9);

      let content =
        d.group === "location"
          ? `<strong>${d.id}</strong><br/>
       Climbs: ${d.count}<br/>
       Disciplines: ${Array.from(d.disciplines).join(", ")}`
          : `<strong>${d.id}</strong>`;

      tooltip
        .html(content)
        .style("left", event.pageX + 10 + "px")
        .style("top", event.pageY - 28 + "px");
    })
    .on("mouseout", function () {
      d3.select("#network-tooltip")
        .transition()
        .duration(500)
        .style("opacity", 0);
    });

  // Update positions on each tick
  simulation.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  });

  // Drag behavior
  function drag(simulation) {
    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return d3
      .drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }
}
