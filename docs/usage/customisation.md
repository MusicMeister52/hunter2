# Customisation

hunter2 has the ability to supply custom script and style on each page, enabling theming. This is simply a matter of
writing your own CSS and/or Javascript; there is no magic to help you apply style to a particular element other than
inspecting the DOM yourself and finding appropriate selectors.

```{warning}
While the maintainers won't change the DOM frivolously, the application is actively developed and some of the HTML
still in use is quite old and expected to change. It is therefore expected that custom styles *will* break to some
extent over time.
```

Style and script exist at the site level and the event level, so if you have a general style and then specific tweaks
such for each event, that is supported. These are set in the *hunter2 Configuration* and *Event* objects in the
Django admin, respectively.

## Trophies

A common use-case for custom style, even if you use the default style elsewhere, is trophy images for winners. After
completing the hunt, the hunt page contains the following:

```html
<div id="event-complete" class="event-completed-1">
    <p>Your team came first!</p>
</div>
```

(the number and text of course changes according to where the team came.) You can customise this to display a banner
image by uploading the image as a file under the name `winner_1.png` for example, and adding the following custom
CSS to the style:

```css
.event-completed-1 {
    background: url('/media/site/winner_1.png') no-repeat;
    background-size: contain;
    width: 800px;
    height: 800px;
}

.event-completed-1 p {
    display: none;
}
```

If you want to use the same image for every event, you'd upload a site file and put this in the site-wide style;
if you want to change it for each event, upload an event file and put this in the event's style. You are of course
able to add banners and specific styles for as many positions as you want by adding styles for `event-completed-2`
and so on.

## Notification Sound

Users can enable sounds to notify them when something happens on a puzzle they are not actively looking at (because they
are manipulating something in an image editor, or have got bored, for example). These sounds are added to the page as
something like:
```html
<audio id="notification-sound">
    <source src="..." type="audio/ogg">
    <source src="..." type="audio/mpeg">
</audio>
```
You can upload event files and your custom script can override the sound files with something like:
```js
document.querySelector('#notification-sound source[type="audio/ogg"').src = '/media/events/1/special_ping.ogg';
document.querySelector('#notification-sound source[type="audio/mp3"').src = '/media/events/1/special_ping.mp3';
```
Make sure you check what formats are actually provided and override all sound files.
