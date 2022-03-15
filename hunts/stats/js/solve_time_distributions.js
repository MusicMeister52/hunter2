import {
  Chart,
  LineElement,
  PointElement,
  LineController,
  CategoryScale,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
} from 'chart.js'
import 'chartjs-adapter-luxon'
import {Duration} from 'luxon'

Chart.register(
  LineElement,
  PointElement,
  LineController,
  CategoryScale,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
)
import { BoxPlotController, BoxAndWiskers, Violin, ViolinController } from '@sgratzl/chartjs-chart-boxplot'
Chart.register(BoxPlotController, BoxAndWiskers, Violin, ViolinController, LinearScale, CategoryScale)

function formatTimeLabel(val) {
  let time = Duration.fromMillis(val * 1000)
  return time.toFormat('hh:mm:ss')
}

// tick increments in seconds
const increments = [
  5 * 60, 10 * 60, 15 * 60, 20 * 60, 30 * 60, 60 * 60,
]
// maximum number of ticks we ideally want to see. This is a soft max - ChartJS won't render them if they're
// overlapping, so allow there to be more to keep the interval at 1h
const maxSteps = 12

function getStepSize(max) {
  for (let increment of increments) {
    if (max / increment < maxSteps) {
      return increment
    }
  }
  return increments[increments.length - 1]
}

function getChartDataSets(episode_data, team) {
  let datasets = []
  if (team !== undefined) {
    datasets.push({
      label: 'My Team',
      type: 'line',
      showLine: false,
      backgroundColor: 'rgba(0, 0, 255, 0.5)',
      borderColor: 'blue',
      borderWidth: 1,
      pointBackgroundColor: 'rgba(0, 0, 255, 0.5)',
      pointBorderColor: 'blue',
      pointBorderWidth: 1,
      data: episode_data.map((p) => (p.solve_times[team])),
    })
  }
  datasets.push({
    label: 'Solve Time',
    type: 'violin',
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    borderColor: 'black',
    borderWidth: 1,
    outlierColor: 'red',
    padding: 10,
    itemRadius: 1,
    itemBackgroundColor: 'rgba(0, 0, 0, 0.2)',
    itemBorderColor: 'rgba(0, 0, 0, 0)',
    meanBackgroundColor: 'rgba(0, 0, 0, 0.3)',
    meanBorderColor: 'rgba(0, 0, 0, 0.5)',
    data: episode_data.map((p) => (Object.values(p.solve_times))),
    '90%': episode_data.map((p) => p['90%']),
  })
  return datasets
}

for (let canvas of document.getElementsByClassName('solve-time-distributions-graph')) {
  let episode_data = window.episode_distributions[canvas.dataset.episode]
  let team = window.my_team
  let datasets = getChartDataSets(episode_data.puzzles, team)

  let height = 0.2 * window.innerHeight
  canvas.height = height
  canvas.style.height = height

  let max = episode_data.max
  let stepSize = getStepSize(max)

  let ctx = canvas.getContext('2d')
  new Chart(ctx, {
    type: 'violin',
    data: {
      labels: episode_data.puzzles.map((p) => (p.title)),
      datasets: datasets,
    },
    options: {
      points: 500,
      minStats: 'min',
      maxStats: 'q3',
      response: true,
      legend: {
        position: 'top',
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function(context) {
              if (team !== undefined && context.datasetIndex === 0) {
                return `${context.dataset.label}: ${formatTimeLabel(context.parsed.y)}`
              } else {
                let vals = context.parsed
                return `fastest: ${formatTimeLabel(vals.min)}, ` +
                  `median: ${formatTimeLabel(vals.median)}, ` +
                  `mean: ${formatTimeLabel(vals.mean)}, ` +
                  `90%: ${formatTimeLabel(context.dataset['90%'][context.dataIndex])}`
              }
            },
          },
        },
      },
      scales: {
        y: {
          ticks: {
            callback: formatTimeLabel,
            stepSize: stepSize,
          },
        },
      },
      title: {
        display: false,
      },
    },
  })
}
