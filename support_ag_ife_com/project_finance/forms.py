from django import forms

from .models import MicrositeProject, PriceItem, Task


class ProjectForm(forms.ModelForm):
    class Meta:
        model = MicrositeProject
        fields = ['name', 'description', 'status']


class PriceItemForm(forms.ModelForm):
    class Meta:
        model = PriceItem
        fields = ['name', 'price', 'is_negotiable']

    def clean(self):
        data = super().clean()
        if data.get('is_negotiable'):
            data['price'] = None
        elif data.get('price') is None:
            self.add_error('price', 'Укажите цену или отметьте «По договорённости».')
        elif data['price'] < 0:
            self.add_error('price', 'Цена не может быть отрицательной.')
        return data


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['price_item', 'title', 'description', 'price', 'quantity', 'time_spent', 'date', 'is_free', 'is_paid']

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        # Услугу можно выбрать только из прайса этого проекта
        self.fields['price_item'].queryset = project.price_items.all()

    def clean(self):
        data = super().clean()
        price = data.get('price')
        if price is None and not data.get('is_free'):
            self.add_error('price', 'Укажите цену. Для бесплатной задачи отметьте «Не включать в стоимость».')
        elif price is not None and price < 0:
            self.add_error('price', 'Цена не может быть отрицательной.')
        if data.get('quantity') is not None and data['quantity'] < 1:
            self.add_error('quantity', 'Количество — не меньше 1.')
        return data
