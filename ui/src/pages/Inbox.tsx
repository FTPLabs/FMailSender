import { Info, Inbox as InboxIcon } from 'lucide-react'

  export default function Inbox() {
    return (
      <div className="space-y-5 animate-fade-in max-w-2xl">
        <div>
          <h1 className="text-2xl font-bold text-text">Входящие</h1>
          <p className="text-muted text-sm mt-1">Bounce, ответы и уведомления</p>
        </div>

        <div className="card flex items-start gap-4 border-cyan/20 bg-cyan/5">
          <Info size={18} className="text-cyan mt-0.5 flex-shrink-0" />
          <div className="text-sm text-muted">
            <p className="text-text font-medium mb-1">IMAP мониторинг</p>
            <p>
              Для получения bounce и ответов укажите IMAP настройки для каждого аккаунта
              во вкладке <span className="text-purple">Аккаунты</span>. 
              Функция будет запущена в следующем обновлении.
            </p>
          </div>
        </div>

        <div className="card text-center py-16 text-muted">
          <InboxIcon size={48} className="mx-auto mb-3 opacity-20" />
          <p className="text-lg font-medium mb-1">Inbox пока пуст</p>
          <p className="text-sm">После запуска рассылки bounce и ответы появятся здесь</p>
        </div>
      </div>
    )
  }
  