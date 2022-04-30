import {format, formatDistanceToNow, isFuture} from 'date-fns'

export default {
  props: ['value', 'title'],
  computed: {
    localeValue() {
      return format(new Date(this.value), 'PPPPpppp')
    },
    distanceToNow() {
      const date = new Date(this.value)
      const [prefix, suffix] = isFuture(date) ? ['in ', ''] : ['', ' ago']
      return `${prefix}${formatDistanceToNow(date)}${suffix}`
    },
  },
}
