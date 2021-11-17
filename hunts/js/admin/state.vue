<template>
    <svg width="2em" height="2em" :title="hover_info">
        <g transform="translate(2 2)">
            <circle v-if="state.state == 'not_opened'"
                :cx="size/2"
                :cy="size/2"
                :r="size/2"
                fill-opacity="0.1"
                stroke="#666"
                stroke-opacity="0.2"
                stroke-width="2"
            />
            <g v-else-if="state.state == 'solved'">
                <circle
                    :cx="size/2"
                    :cy="size/2"
                    :r="size/2"
                    fill="#090"
                    fill-opacity="0.25"
                    stroke="#090"
                    stroke-opacity="0.5"
                    stroke-width="2"
                />
                <text :x="size/2"
                    :y="size/2"
                    text-anchor="middle"
                    dominant-baseline="middle"
                    fill="#080"
                >✔</text>
            </g>
            <g v-else>
                <path
                    :title="state.latest_guess"
                    fill="red"
                    :fill-opacity="activeOpacity(state.latest_guess)"
                    stroke="#622"
                    stroke-opacity="0.5"
                    stroke-width="2px"
                    :d="drawPie(state.time_on)"
                />
                <text v-if="!state.hints_scheduled"
                    :x="size/2 - 6"
                    :y="size/2"
                    text-anchor="middle"
                    dominant-baseline="middle"
                    font-weight="bold"
                    font-size="150%"
                >!</text>
            </g>
        </g>
    </svg>
</template>
<script>
import DateTime from 'luxon/src/datetime.js'

export default {
  props: ['state', 'row', 'col'],
  computed: {
    hover_info: function() {
      return `${this.state.guesses} guesses`
    }
  },
  data: function () {
    return {
      size: 25,
    }
  },
  methods: {
    activeOpacity: function(time) {
      if (time === null) {
        return 0
      }
      var dur = -DateTime.fromISO(time).diffNow().as('seconds')
      var opacity = 1.0 / ((dur / 600) + 1)
      return opacity
    },
    drawPie: function(amount) {
      var size = 25
      var proportion = 0
      if (amount != 0) {
        // proportion = 1-Math.exp(-amount/10)
        // proportion = 1-Math.pow(1.5, -Math.log(1+amount)/Math.log(15))
        proportion = 1 - 1/(1+amount/3600)
        // proportion = Math.log2(amount)
      }
      var angle = (proportion * Math.PI * 2) - Math.PI / 2
      var x = Math.cos(angle) * size/2 + size/2
      var y = Math.sin(angle) * size/2 + size/2
      var large = (proportion < 0.5) ? 0 : 1
      var pathString = 'M ' + size / 2 + ', ' + size/2 +
        'l 0, ' + (-size/2).toString() +
        'A ' + size/2 + ',' + size/2 + ' 0 ' + large + ' ' + ' 1 ' + x + ',' + y +
        'z'
      return pathString
    },
  }
}
</script>
