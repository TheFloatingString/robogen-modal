'use client';

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

interface SubstepWithClusters {
  text: string;
  clusters: {
    [key: string]: number;
  };
}

interface SubstepData {
  dirname: string;
  substeps: SubstepWithClusters[];
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  tasks: Set<string>;
  frequency: number;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  frequency: number;
}

interface ClusterSummary {
  summary: string;
  size: number;
  examples: string[];
}

interface ClusteringData {
  metadata: {
    total_unique_substeps: number;
    total_entries: number;
    k_values: number[];
    embedding_model: string;
    summary_model: string;
  };
  data: SubstepData[];
  cluster_summaries: {
    [key: string]: {
      [clusterKey: string]: ClusterSummary;
    };
  };
}

export default function NetworkGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<SubstepData[]>([]);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(false);
  const [maxEdgeFrequency, setMaxEdgeFrequency] = useState(1);
  const [maxNodeDegree, setMaxNodeDegree] = useState(1);
  const [showLongestPath, setShowLongestPath] = useState(false);
  const [longestPaths, setLongestPaths] = useState<string[][]>([]);
  const [top1000Paths, setTop1000Paths] = useState<string[][]>([]);
  const [selectedPathIndex, setSelectedPathIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [animationPathIndex, setAnimationPathIndex] = useState(0);
  const animationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [nodeGradient, setNodeGradient] = useState('');
  const [edgeGradient, setEdgeGradient] = useState('');
  const [clusteringData, setClusteringData] = useState<ClusteringData | null>(null);
  const [showEmbeddings, setShowEmbeddings] = useState(false);
  const [currentK, setCurrentK] = useState(2);
  const [graphReady, setGraphReady] = useState(false);
  const [dataSource, setDataSource] = useState<'embedding' | 'gpt' | 'drop-first-word' | 'drop-first-word-k10-20' | 'k10-20-drop-first-word' | 'hierarchical-kmeans' | 'spectral' | 'human-labeled'>('embedding');

  // Load clustering data based on dataSource state
  useEffect(() => {
    const jsonFile = dataSource === 'gpt'
      ? '/clustering_results_gpt_5.2.json'
      : dataSource === 'drop-first-word'
      ? '/clustering_results.-drop_first_word.json'
      : dataSource === 'drop-first-word-k10-20'
      ? '/clustering_results-k10-20.json'
      : dataSource === 'k10-20-drop-first-word'
      ? '/clustering_results_k10-20-drop_first_word.json'
      : dataSource === 'hierarchical-kmeans'
      ? '/clustering_results_hierarchical-kmeans_k3-20.json'
      : dataSource === 'spectral'
      ? '/clustering_results_spectral_k3-20.json'
      : dataSource === 'human-labeled'
      ? '/clustering_results_human_labeled_k9.json'
      : '/clustering_results.json';

    setLoading(true);
    fetch(jsonFile)
      .then((res) => res.json())
      .then((json) => {
        setClusteringData(json);
        setData(json.data);
        setLoading(false);
        console.log(`Loaded clustering data from ${jsonFile}:`, json);

        // Set currentK to the minimum available k value
        if (json.metadata?.k_values?.length > 0) {
          const minK = Math.min(...json.metadata.k_values);
          setCurrentK(minK);
        }
      })
      .catch((err) => {
        console.error(`Error loading clustering data from ${jsonFile}:`, err);
        setLoading(false);
      });
  }, [dataSource]);

  // Keyboard listener for 'L' key to toggle dark mode, '1-9' for longest paths, 'j' for animation, 'e' for embeddings, 'u'/'i' for k adjustment, 'c' for clustering data
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'l' || event.key === 'L') {
        setDarkMode((prev) => !prev);
      } else if (event.key === 'j' || event.key === 'J') {
        // Toggle animation
        setIsAnimating((prev) => !prev);
      } else if (event.key === 'e' || event.key === 'E') {
        // Toggle embedding view
        setShowEmbeddings((prev) => !prev);
      } else if (event.key === 'c' || event.key === 'C') {
        // Cycle through clustering data sources
        setDataSource((prev) => {
          if (prev === 'embedding') return 'gpt';
          if (prev === 'gpt') return 'drop-first-word';
          if (prev === 'drop-first-word') return 'drop-first-word-k10-20';
          if (prev === 'drop-first-word-k10-20') return 'k10-20-drop-first-word';
          if (prev === 'k10-20-drop-first-word') return 'hierarchical-kmeans';
          if (prev === 'hierarchical-kmeans') return 'spectral';
          if (prev === 'spectral') return 'human-labeled';
          return 'embedding';
        });
      } else if (event.key === 'u' || event.key === 'U') {
        // Decrease k value
        if (clusteringData?.metadata?.k_values) {
          const kValues = clusteringData.metadata.k_values.sort((a, b) => a - b);
          const currentIndex = kValues.indexOf(currentK);
          if (currentIndex > 0) {
            setCurrentK(kValues[currentIndex - 1]);
          }
        }
      } else if (event.key === 'i' || event.key === 'I') {
        // Increase k value
        if (clusteringData?.metadata?.k_values) {
          const kValues = clusteringData.metadata.k_values.sort((a, b) => a - b);
          const currentIndex = kValues.indexOf(currentK);
          if (currentIndex < kValues.length - 1) {
            setCurrentK(kValues[currentIndex + 1]);
          }
        }
      } else if (event.key >= '1' && event.key <= '9') {
        const pathNumber = parseInt(event.key);
        const pathIndex = pathNumber - 1;

        if (pathIndex < longestPaths.length) {
          // Stop animation if running
          if (isAnimating) {
            setIsAnimating(false);
          }

          if (showLongestPath && selectedPathIndex === pathIndex) {
            // Toggle off if clicking the same path
            setShowLongestPath(false);
          } else {
            setSelectedPathIndex(pathIndex);
            setShowLongestPath(true);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [longestPaths, showLongestPath, selectedPathIndex, isAnimating, clusteringData, currentK]);

  // Animation effect for cycling through top 1000 paths from shortest to longest
  useEffect(() => {
    if (isAnimating && top1000Paths.length > 0) {
      setShowLongestPath(true);

      // Start from shortest (last index in top1000Paths since sorted longest to shortest)
      let currentIndex = top1000Paths.length - 1;
      setAnimationPathIndex(currentIndex);

      animationIntervalRef.current = setInterval(() => {
        currentIndex--;

        if (currentIndex < 0) {
          // Reached the end (longest path), stop animation
          setIsAnimating(false);
          return;
        }

        setAnimationPathIndex(currentIndex);
      }, 100); // 0.1s = 100ms

      return () => {
        if (animationIntervalRef.current) {
          clearInterval(animationIntervalRef.current);
          animationIntervalRef.current = null;
        }
      };
    } else if (!isAnimating && animationIntervalRef.current) {
      // Stop animation
      clearInterval(animationIntervalRef.current);
      animationIntervalRef.current = null;
    }
  }, [isAnimating, top1000Paths]);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    // Initial theme colors
    const getTheme = (isDark: boolean) => ({
      nodeStroke: isDark ? '#1e293b' : '#fff',
      svgBg: isDark ? '#000000' : '#ffffff',
    });

    const currentTheme = getTheme(darkMode);

    // Process data to create nodes and links
    const nodeMap = new Map<string, GraphNode>();
    const linkMap = new Map<string, GraphLink>();

    data.forEach((item) => {
      if (item.substeps.length === 0) return;

      item.substeps.forEach((substep, index) => {
        const substepText = substep.text;

        // Add or update node
        if (!nodeMap.has(substepText)) {
          nodeMap.set(substepText, {
            id: substepText,
            tasks: new Set([item.dirname]),
            frequency: 1,
          });
        } else {
          const node = nodeMap.get(substepText)!;
          node.tasks.add(item.dirname);
          node.frequency += 1;
        }

        // Add or update link to next substep
        if (index < item.substeps.length - 1) {
          const nextSubstepText = item.substeps[index + 1].text;
          const linkKey = `${substepText}→${nextSubstepText}`;

          if (!linkMap.has(linkKey)) {
            linkMap.set(linkKey, {
              source: substepText,
              target: nextSubstepText,
              frequency: 1,
            });
          } else {
            linkMap.get(linkKey)!.frequency += 1;
          }
        }
      });
    });

    const nodes = Array.from(nodeMap.values());
    const links = Array.from(linkMap.values());

    // Calculate node degrees (number of edges connected to each node)
    const nodeDegreeMap = new Map<string, number>();
    nodes.forEach((node) => nodeDegreeMap.set(node.id, 0));
    links.forEach((link) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      nodeDegreeMap.set(sourceId, (nodeDegreeMap.get(sourceId) || 0) + 1);
      nodeDegreeMap.set(targetId, (nodeDegreeMap.get(targetId) || 0) + 1);
    });

    // Add degree to nodes
    nodes.forEach((node) => {
      (node as any).degree = nodeDegreeMap.get(node.id) || 0;
    });

    const calculatedMaxNodeFrequency = d3.max(nodes, (d) => d.frequency) || 1;
    const maxLinkFrequency = d3.max(links, (d) => d.frequency) || 1;

    // Generate gradient strings for legend
    const generateGradient = (steps: number, isDark: boolean, type: 'node' | 'edge') => {
      const colors: string[] = [];
      for (let i = 0; i <= steps; i++) {
        const ratio = steps > 0 ? i / steps : 0;
        let t: number;
        let color: string;
        if (type === 'node') {
          // Node uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxNodeFrequency]
          const freq = 1 + ratio * (calculatedMaxNodeFrequency - 1);
          t = calculatedMaxNodeFrequency > 1 ? (freq - 1) / (calculatedMaxNodeFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        } else {
          // Edge uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxLinkFrequency]
          const freq = 1 + ratio * (maxLinkFrequency - 1);
          t = maxLinkFrequency > 1 ? (freq - 1) / (maxLinkFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        }
        colors.push(color);
      }
      return `linear-gradient(to right, ${colors.join(', ')})`;
    };

    const nodeGrad = generateGradient(10, darkMode, 'node');
    const edgeGrad = generateGradient(10, darkMode, 'edge');

    // Update state for legend
    setMaxNodeDegree(calculatedMaxNodeFrequency);
    setMaxEdgeFrequency(maxLinkFrequency);
    setNodeGradient(nodeGrad);
    setEdgeGradient(edgeGrad);

    // Find all paths in the graph using DFS
    const findAllPaths = () => {
      // Build adjacency list
      const adjacencyList = new Map<string, string[]>();

      nodes.forEach(node => {
        adjacencyList.set(node.id, []);
      });

      links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        adjacencyList.get(sourceId)?.push(targetId);
      });

      // DFS to find all paths from a given node
      const allPathsFromNode: string[][] = [];

      const dfs = (node: string, visited: Set<string>, path: string[]) => {
        visited.add(node);
        path.push(node);

        const neighbors = adjacencyList.get(node) || [];
        let hasUnvisitedNeighbor = false;

        for (const neighbor of neighbors) {
          if (!visited.has(neighbor)) {
            hasUnvisitedNeighbor = true;
            dfs(neighbor, visited, [...path]);
          }
        }

        // If no unvisited neighbors, this is a terminal path
        if (!hasUnvisitedNeighbor) {
          allPathsFromNode.push([...path]);
        }

        visited.delete(node);
      };

      // Try starting from all nodes to collect all maximal paths
      nodes.forEach(node => {
        dfs(node.id, new Set(), []);
      });

      // Get unique paths
      const uniquePaths = new Map<string, string[]>();
      allPathsFromNode.forEach(path => {
        const key = path.join('→');
        if (!uniquePaths.has(key)) {
          uniquePaths.set(key, path);
        }
      });

      // Sort paths by length descending (longest to shortest)
      const allSortedPaths = Array.from(uniquePaths.values())
        .sort((a, b) => b.length - a.length);

      const top9Paths = allSortedPaths.slice(0, 9);
      const top1000Paths = allSortedPaths.slice(0, 1000);

      return { allPaths: allSortedPaths, top9: top9Paths, top1000: top1000Paths };
    };

    const { allPaths: allFoundPaths, top9, top1000 } = findAllPaths();
    console.log(`Found ${allFoundPaths.length} total unique paths`);
    console.log('Top 9 longest paths:');
    top9.forEach((path, idx) => {
      console.log(`${idx + 1}. Length ${path.length}:`, path);
    });
    console.log(`Will animate through top ${top1000.length} paths`);
    console.log('Shortest in top 1000:', top1000[top1000.length - 1]?.length, 'nodes');
    console.log('Longest path:', top1000[0]?.length, 'nodes');
    setTop1000Paths(top1000);
    setLongestPaths(top9);

    // Clear previous SVG content
    d3.select(svgRef.current).selectAll('*').remove();

    // Set up SVG
    const width = 1400;
    const height = 900;
    const svg = d3
      .select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .style('background-color', currentTheme.svgBg);

    // Add zoom behavior
    const g = svg.append('g')
      .style('opacity', 0); // Start invisible

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        }) as any
    );

    // Create arrow markers for each frequency level with matching colors
    const defs = svg.append('defs');
    for (let i = 1; i <= maxLinkFrequency; i++) {
      const t = maxLinkFrequency > 1 ? (i - 1) / (maxLinkFrequency - 1) : 0;
      // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      defs
        .append('marker')
        .attr('id', `arrow-${i}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('class', `arrow-path-${i}`)
        .attr('fill', color);
    }

    // Create force simulation with 4x attraction and 2x centering force
    const simulation = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(25) // Reduced from 50 to 25 for 4x attraction (2x more than before)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(2)) // 2x centering force
      .force('collision', d3.forceCollide().radius(30))
      .alpha(1) // Start with higher energy
      .alphaDecay(0.02); // Slower decay for smoother settling

    // Create links with color scheme (magma 0.9 to 0.5 for light, viridis for dark)
    const link = g
      .append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'graph-link')
      .attr('data-frequency', (d) => d.frequency)
      .attr('data-max-frequency', maxLinkFrequency)
      .attr('data-source', (d) => typeof d.source === 'string' ? d.source : d.source.id)
      .attr('data-target', (d) => typeof d.target === 'string' ? d.target : d.target.id)
      .attr('stroke', (d) => {
        const t = maxLinkFrequency > 1 ? (d.frequency - 1) / (maxLinkFrequency - 1) : 0;
        // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
        return darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
      })
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.8)
      .attr('marker-end', (d) => `url(#arrow-${d.frequency})`);

    // Create tooltip
    const tooltip = d3
      .select('body')
      .append('div')
      .attr('class', 'graph-tooltip')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background-color', darkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(0, 0, 0, 0.9)')
      .style('color', 'white')
      .style('padding', '12px')
      .style('border-radius', '8px')
      .style('font-size', '12px')
      .style('max-width', '400px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('line-height', '1.4')
      .style('border', darkMode ? '1px solid rgba(96, 165, 250, 0.3)' : 'none');

    // Helper function to get cluster color
    const getClusterColor = (clusterId: number, numClusters: number) => {
      // Use distinct colors for clusters
      if (numClusters > 10) {
        // For more than 10 clusters, use rainbow interpolation
        const t = numClusters > 1 ? clusterId / (numClusters - 1) : 0;
        return d3.interpolateRainbow(t);
      }
      // Use schemeCategory10 directly as an array
      return d3.schemeCategory10[clusterId % 10];
    };

    // Build cluster assignments from the substeps data
    const completeClusterAssignments: {[key: string]: number} = {};
    const clusterKey = `k_${currentK}`;

    // Extract cluster assignments from the substeps data
    data.forEach(item => {
      item.substeps.forEach(substep => {
        const clusterId = substep.clusters[clusterKey];
        if (clusterId !== undefined) {
          completeClusterAssignments[substep.text] = clusterId;
        }
      });
    });

    // Check for missing assignments
    const missingNodes: string[] = [];
    nodes.forEach(node => {
      if (completeClusterAssignments[node.id] === undefined) {
        missingNodes.push(node.id);
        completeClusterAssignments[node.id] = 0; // Fallback to cluster 0
      }
    });

    if (missingNodes.length > 0) {
      console.warn(`Warning: ${missingNodes.length} nodes are missing cluster assignments for k=${currentK}. They will be assigned to cluster 0.`);
      console.warn('First 10 missing nodes:', missingNodes.slice(0, 10));
    }

    // Get cluster summaries
    const clusterSummaries = clusteringData?.cluster_summaries?.[clusterKey] || {};

    // Create nodes with colors based on frequency (magma 0.9 to 0.5 for light, viridis for dark) or cluster
    const node = g
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('class', 'graph-node')
      .attr('r', 16)
      .attr('data-frequency', (d) => d.frequency)
      .attr('data-max-frequency', calculatedMaxNodeFrequency)
      .attr('data-degree', (d: any) => d.degree)
      .attr('data-cluster', (d) => completeClusterAssignments[d.id])
      .attr('fill', (d) => {
        // Use cluster colors if embedding view is enabled
        if (showEmbeddings) {
          return getClusterColor(completeClusterAssignments[d.id], currentK);
        }
        // Otherwise use frequency-based colors
        const t = calculatedMaxNodeFrequency > 1 ? (d.frequency - 1) / (calculatedMaxNodeFrequency - 1) : 0;
        // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
        return darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
      })
      .attr('stroke', currentTheme.nodeStroke)
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Create text labels for cluster names (kept hidden, but available for future use)
    const nodeLabels = g
      .append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('class', 'node-label')
      .attr('text-anchor', 'middle')
      .attr('dy', 25)
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('fill', darkMode ? '#ffffff' : '#000000')
      .attr('pointer-events', 'none')
      .attr('data-cluster', (d) => completeClusterAssignments[d.id])
      .style('display', 'none')
      .text((d) => {
        const clusterId = completeClusterAssignments[d.id];
        const clusterKey = `cluster_${clusterId}`;
        return clusterSummaries[clusterKey]?.summary || `Cluster ${clusterId}`;
      });

    // Add hover effects
    node
      .on('mouseover', (event, d: any) => {
        const tasks = Array.from(d.tasks);
        const displayTasks = tasks.slice(0, 10);
        const remaining = tasks.length - displayTasks.length;

        tooltip
          .style('visibility', 'visible')
          .html(
            `<div style="font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px;">${d.id}</div>
             <div style="margin-bottom: 4px;"><strong>Frequency:</strong> ${d.frequency}</div>
             <div style="margin-bottom: 4px;"><strong>Connections:</strong> ${d.degree} edges</div>
             <div style="margin-bottom: 4px;"><strong>Tasks (${tasks.length}):</strong></div>
             <div style="max-height: 200px; overflow-y: auto; font-size: 10px;">
               ${displayTasks.map((task) => `<div style="margin: 2px 0;">• ${task}</div>`).join('')}
               ${remaining > 0 ? `<div style="margin-top: 4px; font-style: italic;">...and ${remaining} more</div>` : ''}
             </div>`
          );

        // Highlight connected nodes and links
        link
          .attr('stroke-opacity', (l) =>
            (l.source as GraphNode).id === d.id || (l.target as GraphNode).id === d.id ? 1 : 0.1
          )
          .attr('stroke-width', (l) =>
            (l.source as GraphNode).id === d.id || (l.target as GraphNode).id === d.id ? 3 : 2
          );

        node.attr('opacity', (n) => {
          if (n.id === d.id) return 1;
          const isConnected = links.some(
            (l) =>
              ((l.source as GraphNode).id === d.id && (l.target as GraphNode).id === n.id) ||
              ((l.target as GraphNode).id === d.id && (l.source as GraphNode).id === n.id)
          );
          return isConnected ? 1 : 0.2;
        });
      })
      .on('mousemove', (event) => {
        tooltip
          .style('top', event.pageY + 15 + 'px')
          .style('left', event.pageX + 15 + 'px');
      })
      .on('mouseout', () => {
        tooltip.style('visibility', 'hidden');
        link.attr('stroke-opacity', 0.8).attr('stroke-width', 2);
        node.attr('opacity', 1);
      });

    // Update positions on each tick
    let tickCount = 0;
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as GraphNode).x!)
        .attr('y1', (d) => (d.source as GraphNode).y!)
        .attr('x2', (d) => (d.target as GraphNode).x!)
        .attr('y2', (d) => (d.target as GraphNode).y!);

      node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);

      nodeLabels
        .attr('x', (d) => d.x!)
        .attr('y', (d) => d.y!);

      // After initial settling, fade in the graph
      tickCount++;
      if (tickCount === 100) {
        g.transition()
          .duration(800)
          .style('opacity', 1);
        setGraphReady(true);
      }
    });

    // Cleanup
    return () => {
      simulation.stop();
      tooltip.remove();
    };
  }, [data]);

  // Separate effect to update theme colors without re-rendering the graph
  useEffect(() => {
    if (!svgRef.current) return;

    const theme = {
      nodeStroke: darkMode ? '#1e293b' : '#fff',
      svgBg: darkMode ? '#000000' : '#ffffff',
    };

    // Regenerate gradients for legend
    const generateGradient = (steps: number, isDark: boolean, type: 'node' | 'edge') => {
      const colors: string[] = [];
      for (let i = 0; i <= steps; i++) {
        const ratio = steps > 0 ? i / steps : 0;
        let t: number;
        let color: string;
        if (type === 'node') {
          // Node uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxNodeFrequency]
          const freq = 1 + ratio * (maxNodeDegree - 1);
          t = maxNodeDegree > 1 ? (freq - 1) / (maxNodeDegree - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        } else {
          // Edge uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxLinkFrequency]
          const freq = 1 + ratio * (maxEdgeFrequency - 1);
          t = maxEdgeFrequency > 1 ? (freq - 1) / (maxEdgeFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        }
        colors.push(color);
      }
      return `linear-gradient(to right, ${colors.join(', ')})`;
    };

    setNodeGradient(generateGradient(10, darkMode, 'node'));
    setEdgeGradient(generateGradient(10, darkMode, 'edge'));

    // Update SVG background
    d3.select(svgRef.current).style('background-color', theme.svgBg);

    // Helper function to get cluster color
    const getClusterColor = (clusterId: number, numClusters: number) => {
      if (numClusters > 10) {
        const t = numClusters > 1 ? clusterId / (numClusters - 1) : 0;
        return d3.interpolateRainbow(t);
      }
      // Use schemeCategory10 directly as an array
      return d3.schemeCategory10[clusterId % 10];
    };

    // Build current cluster assignments from the substeps data
    const clusterKey = `k_${currentK}`;
    const currentClusterAssignments: {[key: string]: number} = {};

    if (clusteringData?.data) {
      clusteringData.data.forEach(item => {
        item.substeps.forEach(substep => {
          const clusterId = substep.clusters[clusterKey];
          if (clusterId !== undefined) {
            currentClusterAssignments[substep.text] = clusterId;
          }
        });
      });
    }

    const currentClusterSummaries = clusteringData?.cluster_summaries?.[clusterKey] || {};

    // Update node strokes and fills with appropriate colormap or cluster colors
    d3.selectAll('.graph-node').each(function (d: any) {
      const frequency = +(this as SVGCircleElement).getAttribute('data-frequency')!;
      const maxFrequency = +(this as SVGCircleElement).getAttribute('data-max-frequency')!;

      // Update cluster assignment based on current k
      const newClusterId = currentClusterAssignments[d.id] ?? 0;
      d3.select(this).attr('data-cluster', newClusterId);

      let color: string;
      // Use cluster colors if embedding view is enabled
      if (showEmbeddings) {
        color = getClusterColor(newClusterId, currentK);
      } else {
        // Otherwise use frequency-based colors
        const t = maxFrequency > 1 ? (frequency - 1) / (maxFrequency - 1) : 0;
        color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
      }

      d3.select(this)
        .attr('fill', color)
        .attr('stroke', theme.nodeStroke);
    });

    // Update all links with appropriate colormap
    d3.selectAll('.graph-link').each(function () {
      const frequency = +(this as SVGLineElement).getAttribute('data-frequency')!;
      const maxFreq = +(this as SVGLineElement).getAttribute('data-max-frequency')!;
      const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      d3.select(this).attr('stroke', color);
    });

    // Update arrow colors with appropriate colormap
    d3.selectAll('[class^="arrow-path-"]').each(function () {
      const className = (this as SVGPathElement).getAttribute('class')!;
      const frequency = parseInt(className.split('-')[2]);
      const maxFreq = maxEdgeFrequency;
      const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      d3.select(this).attr('fill', color);
    });

    // Update tooltip
    d3.selectAll('.graph-tooltip')
      .style('background-color', darkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(0, 0, 0, 0.9)')
      .style('border', darkMode ? '1px solid rgba(96, 165, 250, 0.3)' : 'none');

    // Update label attributes (but keep hidden)
    d3.selectAll('.node-label').each(function (d: any) {
      // Update cluster assignment
      const newClusterId = currentClusterAssignments[d.id] ?? 0;
      const clusterKey = `cluster_${newClusterId}`;
      const labelText = currentClusterSummaries[clusterKey]?.summary || `Cluster ${newClusterId}`;

      d3.select(this)
        .attr('data-cluster', newClusterId)
        .attr('fill', darkMode ? '#ffffff' : '#000000')
        .style('display', 'none')
        .text(labelText);
    });
  }, [darkMode, maxEdgeFrequency, showEmbeddings, currentK, clusteringData]);

  // Separate effect to highlight longest path
  useEffect(() => {
    if (!svgRef.current) return;

    // Use animation path if animating, otherwise use selected path from top 9
    const currentPath = isAnimating
      ? (top1000Paths[animationPathIndex] || [])
      : (longestPaths[selectedPathIndex] || []);

    // Check if a link is part of the current path
    const isInCurrentPath = (source: string, target: string) => {
      for (let i = 0; i < currentPath.length - 1; i++) {
        if (currentPath[i] === source && currentPath[i + 1] === target) {
          return true;
        }
      }
      return false;
    };

    if (showLongestPath && currentPath.length > 0) {
      // Highlight edges in the current path
      d3.selectAll('.graph-link').each(function () {
        const source = (this as SVGLineElement).getAttribute('data-source')!;
        const target = (this as SVGLineElement).getAttribute('data-target')!;

        if (isInCurrentPath(source, target)) {
          // Highlight this edge
          d3.select(this)
            .attr('stroke', '#00ff00')
            .attr('stroke-width', 5)
            .attr('stroke-opacity', 1);
        } else {
          // Dim other edges
          d3.select(this)
            .attr('stroke-opacity', 0.1);
        }
      });

      // Highlight nodes in the current path
      d3.selectAll('.graph-node').each(function (d: any) {
        if (currentPath.includes(d.id)) {
          d3.select(this)
            .attr('stroke', '#00ff00')
            .attr('stroke-width', 4)
            .attr('opacity', 1);
        } else {
          d3.select(this).attr('opacity', 0.2);
        }
      });
    } else {
      // Reset to normal styling
      const theme = {
        nodeStroke: darkMode ? '#1e293b' : '#fff',
      };

      d3.selectAll('.graph-link').each(function () {
        const frequency = +(this as SVGLineElement).getAttribute('data-frequency')!;
        const maxFreq = +(this as SVGLineElement).getAttribute('data-max-frequency')!;
        const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
        const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

        d3.select(this)
          .attr('stroke', color)
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 0.8);
      });

      d3.selectAll('.graph-node').each(function () {
        const frequency = +(this as SVGCircleElement).getAttribute('data-frequency')!;
        const maxFrequency = +(this as SVGCircleElement).getAttribute('data-max-frequency')!;
        const t = maxFrequency > 1 ? (frequency - 1) / (maxFrequency - 1) : 0;
        const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

        d3.select(this)
          .attr('fill', color)
          .attr('stroke', theme.nodeStroke)
          .attr('stroke-width', 2)
          .attr('opacity', 1);
      });
    }
  }, [showLongestPath, longestPaths, top1000Paths, selectedPathIndex, animationPathIndex, isAnimating, darkMode]);

  if (loading) {
    return (
      <div className={`flex h-screen items-center justify-center ${darkMode ? 'bg-black text-white' : 'bg-white text-gray-900'}`}>
        <div className="text-lg">Loading network graph...</div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-screen transition-colors ${darkMode ? 'bg-black' : 'bg-gray-50'}`}>
      <div className={`shadow-sm p-4 border-b transition-colors ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-gray-200'}`}>
        <div className="flex items-center justify-between">
          <h1 className={`text-2xl font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>
            Substeps Network Graph
          </h1>
          <div className="flex gap-2">
            <div className={`text-xs px-3 py-1 rounded-full ${darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600'}`}>
              Press L to toggle theme
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${dataSource !== 'embedding' ? (darkMode ? 'bg-orange-700 text-orange-200' : 'bg-orange-200 text-orange-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press C to cycle data ({dataSource === 'gpt' ? 'GPT-5.2' : dataSource === 'drop-first-word' ? 'Drop-1st-Word (k2-9)' : dataSource === 'drop-first-word-k10-20' ? 'k10-20' : dataSource === 'k10-20-drop-first-word' ? 'k10-20 Drop-1st-Word' : dataSource === 'hierarchical-kmeans' ? 'Hierarchical K-means (k3-20)' : dataSource === 'spectral' ? 'Spectral (k3-20)' : dataSource === 'human-labeled' ? 'Human-Labeled (k9)' : 'Embedding'})
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${showLongestPath ? (darkMode ? 'bg-green-700 text-green-200' : 'bg-green-200 text-green-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press 1-{longestPaths.length} to show longest paths {showLongestPath && !isAnimating ? `(showing #${selectedPathIndex + 1})` : ''}
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${isAnimating ? (darkMode ? 'bg-purple-700 text-purple-200' : 'bg-purple-200 text-purple-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press J to animate {isAnimating ? `(${top1000Paths.length - animationPathIndex}/${top1000Paths.length})` : '(top 1000 paths)'}
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${showEmbeddings ? (darkMode ? 'bg-cyan-700 text-cyan-200' : 'bg-cyan-200 text-cyan-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press E to toggle embeddings {showEmbeddings ? `(k=${currentK})` : ''}
            </div>
            {showEmbeddings && clusteringData?.metadata?.k_values && clusteringData.metadata.k_values.length > 1 && (
              <div className={`text-xs px-3 py-1 rounded-full ${darkMode ? 'bg-cyan-700 text-cyan-200' : 'bg-cyan-200 text-cyan-800'}`}>
                Press U/I for clusters {(() => {
                  const kValues = clusteringData.metadata.k_values.sort((a, b) => a - b);
                  const currentIndex = kValues.indexOf(currentK);
                  return (currentIndex > 0 ? '▼' : '') + (currentIndex < kValues.length - 1 ? '▲' : '');
                })()}
              </div>
            )}
          </div>
        </div>
        <p className={`text-sm mt-1 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
          Hover over nodes to see task details. Drag nodes to rearrange. Scroll to zoom.
          {clusteringData?.metadata && (
            <span className={`ml-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              • Model: {clusteringData.metadata.embedding_model || 'N/A'}
              • {clusteringData.metadata.total_unique_substeps} unique substeps
            </span>
          )}
          {isAnimating && top1000Paths[animationPathIndex] && (
            <span className={`ml-2 font-semibold ${darkMode ? 'text-purple-300' : 'text-purple-600'}`}>
              Currently showing path with {top1000Paths[animationPathIndex].length} nodes
            </span>
          )}
        </p>
        <div className={`flex flex-col gap-3 mt-3 text-xs ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
          {!showEmbeddings && (
            <>
              <div className="flex items-center gap-3">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold">Node color = frequency:</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px]">1</span>
                    <div className="flex h-3 w-32 rounded overflow-hidden" style={{
                      background: nodeGradient
                    }}></div>
                    <span className="text-[10px]">{maxNodeDegree}</span>
                    <span className="ml-1">occurrences</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold">Edge color = frequency:</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px]">1</span>
                    <div className="flex h-3 w-32 rounded overflow-hidden" style={{
                      background: edgeGradient
                    }}></div>
                    <span className="text-[10px]">{maxEdgeFrequency}</span>
                    <span className="ml-1">occurrences</span>
                  </div>
                </div>
              </div>
            </>
          )}
          {showEmbeddings && clusteringData && (
            <div className="flex items-center gap-3">
              <div className="flex flex-col w-full">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold">Cluster view (k={currentK}):</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(clusteringData.cluster_summaries?.[`k_${currentK}`] || {}).map(([clusterId, summary]) => {
                    const clusterNum = parseInt(clusterId.split('_')[1]);
                    // Get cluster color - use the same logic as in the graph
                    let color: string;
                    if (currentK > 10) {
                      const t = currentK > 1 ? clusterNum / (currentK - 1) : 0;
                      color = d3.interpolateRainbow(t);
                    } else {
                      // Use schemeCategory10 directly as an array
                      color = d3.schemeCategory10[clusterNum % 10];
                    }
                    return (
                      <div key={clusterId} className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: color }}></div>
                        <span className="text-[10px]">{summary.summary} ({summary.size})</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
          {longestPaths.length > 0 && (
            <div className="flex items-center gap-3 mt-2">
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">Available paths:</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {longestPaths.map((path, idx) => (
                    <div
                      key={idx}
                      className={`text-[10px] px-2 py-1 rounded ${
                        showLongestPath && selectedPathIndex === idx
                          ? isAnimating
                            ? darkMode
                              ? 'bg-purple-700 text-purple-200 font-bold'
                              : 'bg-purple-200 text-purple-800 font-bold'
                            : darkMode
                            ? 'bg-green-700 text-green-200 font-bold'
                            : 'bg-green-200 text-green-800 font-bold'
                          : darkMode
                          ? 'bg-slate-700 text-slate-300'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {idx + 1}: {path.length} nodes
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <svg ref={svgRef} className="w-full h-full"></svg>
      </div>
    </div>
  );
}
